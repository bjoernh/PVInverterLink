/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./solar_backend/templates/**/*.{jinja2,html}",
  ],
  safelist: [
    'text-green-700',
    'text-red-700',
  ],
  theme: {
    extend: {},
  },
  plugins: [
    require('daisyui'),
  ],
  daisyui: {
    themes: ["light", "dark"],
  },
}
