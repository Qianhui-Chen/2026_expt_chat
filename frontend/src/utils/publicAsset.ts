/**
 * public/ 静态资源路径（相对 Vite base）。
 * 使用相对路径，避免写死 `/meet/...` 站根绝对路径导致子目录部署裂图。
 * 配合 HashRouter + vite `base: "./"`，在任意路由下都能正确解析。
 */
export function publicAsset(path: string): string {
  const clean = path.replace(/^\//, "");
  const base = import.meta.env.BASE_URL || "./";
  if (base.endsWith("/")) {
    return `${base}${clean}`;
  }
  return `${base}/${clean}`;
}
