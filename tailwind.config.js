/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./solar_backend/templates/**/*.{jinja2,html}",
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
