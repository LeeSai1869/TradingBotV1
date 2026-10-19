export const name = "reload";
const el = () => document.getElementById("reload");
export function mount() {}
export function bind(onClick) { el().addEventListener("click", onClick); }
