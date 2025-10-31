'use client';

import UploadButton from './UploadButton';
import FileList from './FileList';
import { Ghost, Loader2, MessageSquare, Plus, Trash, File as FileIcon } from 'lucide-react';
import Skeleton from 'react-loading-skeleton';
import Link from 'next/link';
import { format } from 'date-fns';
import { Button } from './ui/button';
import { useEffect, useRef, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { isTauri } from '@/lib/runtime';
import { convertFileSrc } from '@tauri-apps/api/core';

type FileItem = {
  id: string;
  name: string;
  path: string;
  thumbPath?: string | null;
  createdAt: string;
};

const Dashboard = () => {
  const Thumb = ({ fileId }: { fileId: string }) => {
    const videoRef = useRef<HTMLVideoElement | null>(null);
    const canvasRef = useRef<HTMLCanvasElement | null>(null);
    const [poster, setPoster] = useState<string | null>(null);
    const [src, setSrc] = useState<string | null>(null);
    const seekTimes = useRef<number[]>([0.1, 0.5, 1, 2, 3]);
    const attemptIndex = useRef<number>(0);
    const triesLeft = useRef<number>(8);

    useEffect(() => {
      let active = true;
      (async () => {
        try {
          // Prefer blob URL to avoid file:// canvas tainting/cross-origin issues
          const bytes = await (window as any).__TAURI__?.tauri?.invoke('read_file_bytes', { fileId });
          if (!active) return;
          const u8 = new Uint8Array(bytes as number[]);
          const blob = new Blob([u8], { type: 'video/mp4' });
          const url = URL.createObjectURL(blob);
          setSrc(url);
        } catch {
          // Fallback to converted file src if bytes read fails
          try {
            const path = await (window as any).__TAURI__?.tauri?.invoke('get_file_path', { fileId });
            if (!active) return;
            if (path) setSrc(convertFileSrc(path as string));
          } catch {}
        }
      })();
      return () => {
        active = false;
        if (src && src.startsWith('blob:')) URL.revokeObjectURL(src);
      };
    }, [fileId]);

    const tryNextSeek = () => {
      const v = videoRef.current;
      if (!v) return;
      if (attemptIndex.current >= seekTimes.current.length) return;
      try {
        v.currentTime = seekTimes.current[attemptIndex.current++];
      } catch {}
    };

    const drawFrame = () => {
      const v = videoRef.current;
      const c = canvasRef.current;
      if (!v || !c) return false;
      try {
        c.width = v.videoWidth || 160;
        c.height = v.videoHeight || 90;
        const ctx = c.getContext('2d');
        if (!ctx) return false;
        ctx.drawImage(v, 0, 0, c.width, c.height);
        // Quick non-empty check: sample a few pixels
        const data = ctx.getImageData(0, 0, 4, 4).data;
        let allZero = true;
        for (let i = 0; i < data.length; i++) {
          if (data[i] !== 0) { allZero = false; break; }
        }
        if (allZero) return false;
        const url = c.toDataURL('image/jpeg');
        setPoster(url);
        return true;
      } catch {
        return false;
      }
    };

    return (
      <div className="h-full w-full">
        {poster ? (
          <img src={poster} className="h-full w-full object-cover" alt="thumb" />
        ) : (
          <>
            <video
              ref={videoRef}
              src={src ?? ''}
              muted
              playsInline
              preload="metadata"
              crossOrigin="anonymous"
              className="h-full w-full object-cover"
              onLoadedMetadata={() => {
                attemptIndex.current = 0;
                tryNextSeek();
              }}
              onLoadedData={() => {
                // Try drawing once data is available
                if (!drawFrame()) tryNextSeek();
              }}
              onCanPlay={() => {
                // As a fallback, poll a few times in case seek events are flaky
                if (poster) return;
                if (triesLeft.current <= 0) return;
                const id = setInterval(() => {
                  if (poster) { clearInterval(id); return; }
                  if (drawFrame()) { clearInterval(id); return; }
                  triesLeft.current -= 1;
                  if (triesLeft.current <= 0) clearInterval(id);
                }, 150);
              }}
              onSeeked={() => {
                // If drawing failed, attempt next seek position
                if (!drawFrame()) {
                  tryNextSeek();
                }
              }}
              onError={async () => {
                // Ultimate fallback: ask backend to generate a jpg via ffmpeg
                try {
                  const path = await (window as any).__TAURI__?.tauri?.invoke('generate_thumbnail', { fileId });
                  if (path) setPoster(convertFileSrc(path as string));
                } catch {}
              }}
            />
            <canvas ref={canvasRef} className="hidden" />
          </>
        )}
      </div>
    );
  };
  // Listing moved to FileList component to simplify and isolate bridge issues

  return (
    <main className="mx-auto max-w-7xl md:p-10">
      <div className="mt-8 flex flex-col items-start justify-between gap-4 border-b border-gray-200 pb-5 sm:flex-row sm:items-center sm:gap-0">
        <h1 className="mb-3 font-bold text-5xl text-gray-900">My Files</h1>

        <UploadButton />
      </div>

      <FileList />
    </main>
  );
};

export default Dashboard;