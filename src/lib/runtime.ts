export const isTauri = () =>
    typeof window !== 'undefined' && typeof (window as any).__TAURI__ !== 'undefined';