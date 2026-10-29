import { defineConfig } from 'vitepress'

export default defineConfig({
  title: "Agent Preview Hub",
  description: "Self-hosted interactive preview engine, Mermaid Studio, and Markdown/Diff viewer",
  themeConfig: {
    nav: [
      { text: 'Home', link: '/' },
      { text: 'Architecture', link: '/architecture' }
    ],
    sidebar: [
      {
        text: 'Guide',
        items: [
          { text: 'Overview', link: '/' },
          { text: 'System Architecture', link: '/architecture' }
        ]
      }
    ],
    outline: [2, 3]
  }
})
