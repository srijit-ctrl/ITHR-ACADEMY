/** @type {import('tailwindcss').Config} */
module.exports = {
    darkMode: ["class"],
    content: [
        "./src/**/*.{js,jsx,ts,tsx}",
        "./public/index.html",
    ],
    theme: {
        extend: {
            fontFamily: {
                /* User directive: Calibri (Microsoft-installed) or Tahoma.
                   No CDN webfonts — both ship natively on Windows/macOS/Linux
                   (Calibri on Windows/Office installs, Tahoma everywhere).
                   Headings/subheadings use Tahoma (font-serif kept as an alias
                   so all existing font-serif className usages resolve to Tahoma
                   without a global sweep). */
                serif: ['Tahoma', 'Calibri', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'system-ui', 'sans-serif'],
                sans: ['Calibri', '"Public Sans"', 'Tahoma', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'system-ui', 'sans-serif'],
                label: ['Calibri', 'Tahoma', '"Segoe UI"', 'system-ui', 'sans-serif'],
                mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
            },
            borderRadius: {
                lg: 'var(--radius)',
                md: 'calc(var(--radius) - 2px)',
                sm: 'calc(var(--radius) - 4px)',
            },
            colors: {
                background: 'hsl(var(--background))',
                foreground: 'hsl(var(--foreground))',
                surface: {
                    DEFAULT: 'hsl(var(--surface))',
                    alt: 'hsl(var(--surface-alt))',
                },
                brand: {
                    DEFAULT: 'hsl(var(--brand))',
                    hover: 'hsl(var(--brand-hover))',
                    ink: 'hsl(var(--brand-ink))',
                    blue: 'hsl(var(--brand-blue))',
                    'blue-light': 'hsl(var(--brand-blue-light))',
                    purple: 'hsl(var(--brand-purple))',
                    'purple-light': 'hsl(var(--brand-purple-light))',
                    orange: 'hsl(var(--brand-orange))',
                    'orange-light': 'hsl(var(--brand-orange-light))',
                    teal: 'hsl(var(--brand-teal))',
                    'teal-light': 'hsl(var(--brand-teal-light))',
                    navy: 'hsl(var(--brand-navy))',
                    'navy-deep': 'hsl(var(--brand-navy-deep))',
                    bright: 'hsl(var(--brand-bright))',
                    sky: 'hsl(var(--brand-sky))',
                    'sky-light': 'hsl(var(--brand-sky-light))',
                    gold: 'hsl(var(--brand-gold))',
                    'gold-deep': 'hsl(var(--brand-gold-deep))',
                },
                card: {
                    DEFAULT: 'hsl(var(--card))',
                    foreground: 'hsl(var(--card-foreground))',
                },
                popover: {
                    DEFAULT: 'hsl(var(--popover))',
                    foreground: 'hsl(var(--popover-foreground))',
                },
                primary: {
                    DEFAULT: 'hsl(var(--primary))',
                    foreground: 'hsl(var(--primary-foreground))',
                },
                secondary: {
                    DEFAULT: 'hsl(var(--secondary))',
                    foreground: 'hsl(var(--secondary-foreground))',
                },
                muted: {
                    DEFAULT: 'hsl(var(--muted))',
                    foreground: 'hsl(var(--muted-foreground))',
                },
                accent: {
                    DEFAULT: 'hsl(var(--accent))',
                    foreground: 'hsl(var(--accent-foreground))',
                },
                destructive: {
                    DEFAULT: 'hsl(var(--destructive))',
                    foreground: 'hsl(var(--destructive-foreground))',
                },
                success: 'hsl(var(--success))',
                warning: 'hsl(var(--warning))',
                border: 'hsl(var(--border))',
                input: 'hsl(var(--input))',
                ring: 'hsl(var(--ring))',
            },
            keyframes: {
                'accordion-down': { from: { height: '0' }, to: { height: 'var(--radix-accordion-content-height)' } },
                'accordion-up': { from: { height: 'var(--radix-accordion-content-height)' }, to: { height: '0' } },
                'fade-in': { from: { opacity: '0', transform: 'translateY(8px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
                'shimmer': { '0%': { backgroundPosition: '-1000px 0' }, '100%': { backgroundPosition: '1000px 0' } },
            },
            animation: {
                'accordion-down': 'accordion-down 0.2s ease-out',
                'accordion-up': 'accordion-up 0.2s ease-out',
                'fade-in': 'fade-in 0.6s cubic-bezier(0.22, 1, 0.36, 1) both',
                'shimmer': 'shimmer 2.5s linear infinite',
            },
        },
    },
    plugins: [require("tailwindcss-animate")],
};
