'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Plus, MessageSquare, Loader2, Trash, File as FileIcon, Ghost } from 'lucide-react';
import { format } from 'date-fns';
import { Button } from './ui/button';
import { invoke } from '@tauri-apps/api/core';

type FileItem = {
  id: string;
  name: string;
  path: string;
  thumbPath?: string | null;
  createdAt: string;
};

const FileList = () => {
  const [files, setFiles] = useState<FileItem[] | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [currentlyDeletingFile, setCurrentlyDeletingFile] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchFiles = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await invoke<FileItem[]>('list_files');
      setFiles(result ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load files');
      setFiles([]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchFiles();
  }, []);

  const handleDelete = async (id: string) => {
    setCurrentlyDeletingFile(id);
    try {
      // If not in Tauri, this will throw in the catch above
      await invoke('delete_file', { id });
      await fetchFiles();
    } finally {
      setCurrentlyDeletingFile(null);
    }
  };

  if (error) {
    return (
      <div className="mt-4 text-sm text-red-600">{error}</div>
    );
  }

  if (isLoading) {
    return (
      <div className="mt-8 flex items-center gap-2 text-sm text-zinc-700">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading videos...
      </div>
    );
  }

  if (!files || files.length === 0) {
    return (
      <div className="mt-16 flex flex-col items-center gap-2">
        <Ghost className="h-8 w-8 text-zinc-800" />
        <h3 className="font-semibold text-xl">No videos yet</h3>
        <p>Let&apos;s upload your first MP4.</p>
      </div>
    );
  }

  return (
    <ul className="mt-8 grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
      {files
        .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
        .map((file) => (
          <li key={file.id} className="col-span-1 divide-y divide-gray-200 rounded-lg bg-white shadow transition hover:shadow-lg">
            <Link href={`/dashboard/${file.id}`} className="flex flex-col gap-2">
              <div className="pt-6 px-6 flex w-full items-center justify-between space-x-6">
                <div className="h-16 w-24 flex-shrink-0 rounded-md overflow-hidden bg-gradient-to-r from-cyan-500 to-blue-500 grid place-items-center">
                  <FileIcon className="h-6 w-6 text-white" />
                </div>
                <div className="flex-1 truncate">
                  <div className="flex items-center space-x-3">
                    <h3 className="truncate text-lg font-medium text-zinc-900">{file.name}</h3>
                  </div>
                </div>
              </div>
            </Link>

            <div className="px-6 mt-4 grid grid-cols-3 place-items-center py-2 gap-6 text-xs text-zinc-500">
              <div className="flex items-center gap-2">
                <Plus className="h-4 w-4" />
                {format(new Date(file.createdAt), 'MMM yyyy')}
              </div>

              <div className="flex items-center gap-2">
                <MessageSquare className="h-4 w-4" /> mocked
              </div>

              <Button onClick={() => handleDelete(file.id)} size="sm" className="w-full" variant="destructive">
                {currentlyDeletingFile === file.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash className="h-4 w-4" />}
              </Button>
            </div>
          </li>
        ))}
    </ul>
  );
};

export default FileList;


