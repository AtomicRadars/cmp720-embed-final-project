import re
from pathlib import Path

file_path = Path('Core/Src/app/index.html')
content = file_path.read_text(encoding='utf-8')

# 1. Add Tailwind config
if 'tailwind.config' not in content:
    content = content.replace(
        '<script src="https://cdn.tailwindcss.com"></script>',
        '<script src="https://cdn.tailwindcss.com"></script>\n    <script>\n        tailwind.config = {\n            darkMode: "class"\n        }\n    </script>'
    )

# 2. Update Style block
new_style = """    <style>
        body { font-family: 'Inter', sans-serif; transition: background-color 0.3s, color 0.3s; }
        .glass { backdrop-filter: blur(12px); transition: all 0.3s; }
        
        /* Light mode default */
        body { background-color: #f8fafc; color: #0f172a; }
        .glass { background: rgba(255, 255, 255, 0.7); border: 1px solid rgba(0, 0, 0, 0.08); }
        .terminal-bg { background: #f1f5f9; border: 1px solid rgba(0, 0, 0, 0.08); }
        
        /* Dark mode overrides */
        .dark body { background-color: #0f172a; color: #f8fafc; }
        .dark .glass { background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255, 255, 255, 0.1); }
        .dark .terminal-bg { background: #020617; border: none; }
        
        .accent-glow { box-shadow: 0 0 20px rgba(99, 102, 241, 0.3); }
        .scrollbar-hide::-webkit-scrollbar { display: none; }
        input[type="range"] { accent-color: #6366f1; }
        .btn-primary { background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%); transition: all 0.3s ease; color: white; }
        .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(99, 102, 241, 0.5); }
    </style>"""

content = re.sub(r'<style>.*?</style>', new_style, content, flags=re.DOTALL)

# 3. Add toggle button & update header styling
old_header = """        <header class="flex flex-col md:flex-row justify-between items-start md:items-center mb-10 gap-4">
            <div>
                <h1 class="text-3xl font-bold tracking-tight bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">
                    Scheduler Performance Lab
                </h1>
                <p class="text-slate-400 mt-1">Real-time Task Configuration & Benchmark Suite</p>
            </div>
            <div class="flex gap-3">
                <button onclick="saveParams()" class="flex items-center gap-2 px-5 py-2.5 glass rounded-xl hover:bg-slate-800 transition-all font-medium">"""

new_header = """        <header class="flex flex-col md:flex-row justify-between items-start md:items-center mb-10 gap-4">
            <div>
                <h1 class="text-3xl font-bold tracking-tight bg-gradient-to-r from-slate-800 dark:from-white to-slate-500 dark:to-slate-400 bg-clip-text text-transparent">
                    Scheduler Performance Lab
                </h1>
                <p class="text-slate-600 dark:text-slate-400 mt-1">Real-time Task Configuration & Benchmark Suite</p>
            </div>
            <div class="flex gap-3">
                <button onclick="toggleTheme()" class="flex items-center justify-center w-11 h-11 glass rounded-xl hover:bg-slate-200 dark:hover:bg-slate-800 transition-all text-slate-600 dark:text-slate-400" title="Toggle Theme">
                    <i data-lucide="sun" class="w-5 h-5 hidden dark:block"></i>
                    <i data-lucide="moon" class="w-5 h-5 block dark:hidden"></i>
                </button>
                <button onclick="saveParams()" class="flex items-center gap-2 px-5 py-2.5 glass rounded-xl hover:bg-slate-200 dark:hover:bg-slate-800 transition-all font-medium text-slate-700 dark:text-slate-300">"""

content = content.replace(old_header, new_header)

# 4. Update the console container class to have a dynamic border in light mode
old_console_header = """                    <div class="bg-slate-800/50 px-6 py-3 flex justify-between items-center border-b border-white/5">"""
new_console_header = """                    <div class="bg-slate-200/50 dark:bg-slate-800/50 px-6 py-3 flex justify-between items-center border-b border-slate-300/50 dark:border-white/5">"""
content = content.replace(old_console_header, new_console_header)

# 5. Map console text to the theme-aware colors inside log() function
old_log = """        function log(msg, color = 'slate-300') {
            const consoleEl = document.getElementById('console');
            const line = document.createElement('div');
            line.className = `min-h-[1rem] mb-1 text-${color}`;
            line.innerHTML = msg.trim() === "" ? "&nbsp;" : msg;
            consoleEl.appendChild(line);
            consoleEl.scrollTop = consoleEl.scrollHeight;
        }"""

new_log = """        function log(msg, color = 'slate-300') {
            const consoleEl = document.getElementById('console');
            const line = document.createElement('div');
            const colorMap = {
                'slate-300': 'text-slate-700 dark:text-slate-300',
                'indigo-400': 'text-indigo-600 dark:text-indigo-400',
                'emerald-400': 'text-emerald-600 dark:text-emerald-400',
                'red-400': 'text-red-600 dark:text-red-400',
                'amber-400': 'text-amber-600 dark:text-amber-400'
            };
            const colorClass = colorMap[color] || `text-${color}`;
            line.className = `min-h-[1rem] mb-1 ${colorClass}`;
            line.innerHTML = msg.trim() === "" ? "&nbsp;" : msg;
            consoleEl.appendChild(line);
            consoleEl.scrollTop = consoleEl.scrollHeight;
        }"""

content = content.replace(old_log, new_log)

# 6. Add JS theme initialization and toggleTheme function before window.onload
old_onload = """        window.onload = loadParams;"""

new_theme_js = """        // Theme Toggle
        function toggleTheme() {
            document.documentElement.classList.toggle('dark');
            const isDark = document.documentElement.classList.contains('dark');
            localStorage.setItem('theme', isDark ? 'dark' : 'light');
            if (window.updateCharts) updateCharts();
        }
        
        // Initialize Theme
        if (localStorage.theme === 'dark' || (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
            document.documentElement.classList.add('dark');
        } else {
            document.documentElement.classList.remove('dark');
        }

        window.onload = function() {
            loadParams();
            lucide.createIcons();
        };"""

content = content.replace(old_onload, new_theme_js)

# 7. Apply general text color changes for titles and card texts
general_replacements = {
    'text-indigo-400': 'text-indigo-600 dark:text-indigo-400',
    'text-purple-400': 'text-purple-600 dark:text-purple-400',
    'text-emerald-400': 'text-emerald-600 dark:text-emerald-400',
    'text-amber-400': 'text-amber-600 dark:text-amber-400',
    'text-slate-300': 'text-slate-700 dark:text-slate-300',
    'text-slate-400': 'text-slate-600 dark:text-slate-400',
    'text-white': 'text-slate-900 dark:text-white',
    'bg-slate-900/50': 'bg-white/50 dark:bg-slate-900/50',
    'border-slate-700': 'border-slate-300 dark:border-slate-700',
    'bg-slate-700': 'bg-slate-200 dark:bg-slate-700',
}

# Run replacements on element attributes (keeping it safe using regex bounds)
for old, new in general_replacements.items():
    content = re.sub(rf'(?<!dark:)\b{re.escape(old)}\b', new, content)

# 8. Dynamic Chart Colors for Light/Dark mode inside updateCharts()
chart_colors_setup = """            const isDark = document.documentElement.classList.contains('dark');
            const textColor = isDark ? '#94a3b8' : '#475569';
            const gridColor = isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)';
            const schedulers = Object.keys(data.data);"""

content = content.replace("const schedulers = Object.keys(data.data);", chart_colors_setup)

# Update chart configs to use dynamic color variables
content = content.replace("color: '#94a3b8'", "color: textColor")
content = content.replace("color: '#64748b'", "color: textColor")
content = content.replace("'rgba(255,255,255,0.05)'", "gridColor")

file_path.write_text(content, encoding='utf-8')
print("Successfully patched index.html")
