import re
from pathlib import Path

file_path = Path('Core/Src/app/index.html')
content = file_path.read_text(encoding='utf-8')

# 1. Add Tailwind config
if 'tailwind.config' not in content:
    content = content.replace('<script src="https://cdn.tailwindcss.com"></script>', '<script src="https://cdn.tailwindcss.com"></script>\n    <script>\n        tailwind.config = {\n            darkMode: "class"\n        }\n    </script>')

# 2. Update Style block
new_style = """    <style>
        body { font-family: 'Inter', sans-serif; transition: background-color 0.3s, color 0.3s; }
        .glass { backdrop-filter: blur(12px); transition: all 0.3s; }
        
        /* Light mode */
        body { background-color: #f8fafc; color: #0f172a; }
        .glass { background: rgba(255, 255, 255, 0.7); border: 1px solid rgba(0, 0, 0, 0.05); }
        .terminal-bg { background: #f8fafc; border: 1px solid rgba(0,0,0,0.1); }
        
        /* Dark mode */
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

# 3. Add toggle button
toggle_btn = """            <div class="flex gap-3">
                <button onclick="toggleTheme()" class="flex items-center justify-center w-11 h-11 glass rounded-xl hover:bg-slate-200 dark:hover:bg-slate-800 transition-all" title="Toggle Theme">
                    <i data-lucide="sun" class="w-5 h-5 hidden dark:block text-slate-400 hover:text-white"></i>
                    <i data-lucide="moon" class="w-5 h-5 block dark:hidden text-slate-600 hover:text-black"></i>
                </button>"""
content = content.replace('<div class="flex gap-3">', toggle_btn)

# 4. Add JS function
js_code = """        // Theme Toggle
        function toggleTheme() {
            document.documentElement.classList.toggle('dark');
            const isDark = document.documentElement.classList.contains('dark');
            localStorage.setItem('theme', isDark ? 'dark' : 'light');
            if(window.updateCharts) updateCharts(); // Re-render charts for new colors
        }
        
        // Load theme
        if (localStorage.theme === 'dark' || (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
            document.documentElement.classList.add('dark');
        } else {
            document.documentElement.classList.remove('dark');
        }

        lucide.createIcons();"""
content = content.replace('lucide.createIcons();', js_code)

# 5. Replace utility classes for Light/Dark support
replacements = {
    'text-white': 'text-slate-900 dark:text-white',
    'text-slate-400': 'text-slate-600 dark:text-slate-400',
    'text-slate-300': 'text-slate-700 dark:text-slate-300',
    'bg-slate-700': 'bg-slate-300 dark:bg-slate-700',
    'hover:bg-slate-800': 'hover:bg-slate-200 dark:hover:bg-slate-800',
    'bg-slate-800/50': 'bg-slate-200/50 dark:bg-slate-800/50',
    'bg-slate-900/50': 'bg-white/50 dark:bg-slate-900/50',
    'border-slate-700': 'border-slate-300 dark:border-slate-700',
    'text-indigo-400': 'text-indigo-600 dark:text-indigo-400',
    'text-indigo-300': 'text-indigo-700 dark:text-indigo-300',
    'text-purple-400': 'text-purple-600 dark:text-purple-400',
    'text-emerald-400': 'text-emerald-600 dark:text-emerald-400',
    'text-amber-400': 'text-amber-600 dark:text-amber-400',
    'from-white': 'from-slate-800 dark:from-white',
    'to-slate-400': 'to-slate-500 dark:to-slate-400',
    'border-white/5': 'border-black/5 dark:border-white/5',
}

for old, new in replacements.items():
    content = re.sub(r'(?<!dark:)\b' + re.escape(old) + r'\b', new, content)

# 6. Chart text colors need to be dynamic based on theme
chart_colors_update = """
            const isDark = document.documentElement.classList.contains('dark');
            const textColor = isDark ? '#94a3b8' : '#475569';
            const gridColor = isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)';
"""
content = content.replace("const schedulers = Object.keys(data.data);", "const schedulers = Object.keys(data.data);\n" + chart_colors_update)

content = content.replace("color: '#94a3b8'", "color: textColor")
content = content.replace("color: '#64748b'", "color: textColor")
content = content.replace("'rgba(255,255,255,0.05)'", "gridColor")

file_path.write_text(content, encoding='utf-8')
print("Done")
