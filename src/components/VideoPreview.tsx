'use client';

import { useEffect, useState } from 'react';
import { invoke, convertFileSrc } from '@tauri-apps/api/core';

interface VideoPreviewProps {
  fileId: string;
}

const VideoPreview = ({ fileId }: VideoPreviewProps) => {
  const [videoSrc, setVideoSrc] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [triedBlobFallback, setTriedBlobFallback] = useState<boolean>(false);

  useEffect(() => {
    let isMounted = true;
    (async () => {
      try {
        // Prefer Blob URL from bytes to avoid asset:// issues in WebView
        const bytes = await invoke<number[]>('read_file_bytes', { fileId });
        if (!isMounted) return;
        const u8 = new Uint8Array(bytes);
        const blob = new Blob([u8], { type: 'video/mp4' });
        const url = URL.createObjectURL(blob);
        setVideoSrc(url);
      } catch (e) {
        // Fallback to convertFileSrc if byte-read fails
        try {
          const path = await invoke<string | null>('get_file_path', { fileId });
          if (!isMounted) return;
          if (!path) {
            setError('File not found.');
            return;
          }
          const url = convertFileSrc(path);
          setVideoSrc(url);
        } catch (err) {
          const msg = err instanceof Error ? err.message : 'Failed to resolve video path';
          setError(msg);
        }
      }
    })();
    return () => {
      isMounted = false;
    };
  }, [fileId]);

  if (error) {
    return (
      <div className="w-full h-full grid place-items-center bg-white rounded-md shadow p-6 text-sm text-zinc-600">
        {error}
      </div>
    );
  }

  if (!videoSrc) {
    return (
      <div className="w-full h-full grid place-items-center bg-white rounded-md shadow p-6 text-sm text-zinc-600">
        Loading preview...
      </div>
    );
  }

  return (
    <video
      key={videoSrc}
      className="w-full h-full rounded-md bg-black"
      controls
      playsInline
      preload="auto"
      onError={async () => {
        if (!triedBlobFallback) {
          try {
            const bytes = await invoke<number[]>('read_file_bytes', { fileId });
            const u8 = new Uint8Array(bytes);
            const blob = new Blob([u8], { type: 'video/mp4' });
            const url = URL.createObjectURL(blob);
            setTriedBlobFallback(true);
            setVideoSrc(url);
            setError(null);
            return;
          } catch (e) {
            // fall through to set error below
          }
        }
        setError('Failed to play video. Unsupported format or path.');
      }}
    >
      <source src={videoSrc} type="video/mp4" />
    </video>
  );
};

export default VideoPreview;


