import base from "file:///C:/Users/vibha/Downloads/data/dcortex/dcortex_claude/dcortex-platform/apps/canvas/vite.config.ts";
export default { ...base, root: "C:/Users/vibha/Downloads/data/dcortex/dcortex_claude/dcortex-platform/apps/canvas", cacheDir: process.env.RIG_CACHE, server: { port: 5199, strictPort: true, proxy: {} } };
