export const isTauri = () => {
    if (typeof window === 'undefined') return false;
    const w = window as any;
    if (typeof w.__TAURI__ !== 'undefined') return true;
    if (typeof w.__TAURI_INTERNAL__ !== 'undefined') return true;
    const ua = (navigator?.userAgent || '').toLowerCase();
    return ua.includes('tauri');
};