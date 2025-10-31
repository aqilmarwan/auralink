'use client';

import { useState } from 'react';
import { Dialog, DialogContent, DialogTrigger, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { IconArrowRight, IconSearch } from "@tabler/icons-react";
import Dropzone from 'react-dropzone';
import { Cloud, File, Loader2 } from 'lucide-react';
import { Progress } from './ui/progress';
import { useToast } from './ui/use-toast';
import { useRouter } from 'next/navigation';
import { invoke } from '@tauri-apps/api/core';
// Frontend FS plugin not used; we save via a backend Tauri command
import { isTauri } from '@/lib/runtime';

const MAX_UPLOAD_MB = 16; // uniform access for everyone

const UploadDropzone = () => {
  const router = useRouter();

  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const { toast } = useToast();

  const startSimulatedProgress = () => {
    setUploadProgress(0);

    const interval = setInterval(() => {
      setUploadProgress((prevProgress) => {
        if (prevProgress >= 95) {
          clearInterval(interval);
          return prevProgress;
        }
        return prevProgress + 5;
      });
    }, 500);

    return interval;
  };

  const handleFileUpload = async (file: File) => {
    setIsUploading(true);
    const progressInterval = startSimulatedProgress();

    try {
      // Attempt Tauri path; if this is not the desktop app, the calls below will throw and be handled by catch
      // Generate unique file ID
      const fileId = crypto.randomUUID();

      // Save file to app data directory using Tauri FS API
      const arrayBuffer = await file.arrayBuffer();
      const uint8Array = new Uint8Array(arrayBuffer);
      
      const ext = (file.name.split('.').pop() || 'mp4');
      await invoke<string>('save_file_bytes', {
        fileId,
        ext,
        bytes: Array.from(uint8Array),
        name: file.name,
      });

      clearInterval(progressInterval);
      setUploadProgress(100);

      // Navigate to file view
      router.push(`/dashboard/${fileId}`);

      toast({ title: 'Success', description: 'File saved locally' });
    } catch (error) {
      clearInterval(progressInterval);
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Upload failed',
        variant: 'destructive',
      });
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <Dropzone
      multiple={false}
      onDrop={async (acceptedFile) => {
        if (acceptedFile.length === 0) return;
        await handleFileUpload(acceptedFile[0]);
      }}
      maxSize={MAX_UPLOAD_MB * 1024 * 1024}
      accept={{
        'video/mp4': ['.mp4'],
      }}
    >
      {({ getRootProps, getInputProps, acceptedFiles }) => (
        <div
          {...getRootProps()}
          className="border h-64 m-4 border-dashed border-gray-300 rounded-lg"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex flex-col items-center justify-center h-full w-full">
            <div className="relative w-full bg-gray-50 hover:bg-gray-100">
              <IconSearch className="absolute top-3 w-10 left-1 h-6 rounded-full opacity-50 sm:left-3 sm:top-4 sm:h-8" />
              <input
                className="h-12 w-full text-sm text-zinc-700 font-semibold rounded-full border border-zinc-600 pr-12 pl-11 focus:border-zinc-800 focus:outline-none focus:ring-1 focus:ring-zinc-800 sm:h-16 sm:py-2 sm:pr-16 sm:pl-16 sm:text-lg"
                type="text" 
                placeholder='Paste Your MP4 Link Here'
              />
              <button>
                <IconArrowRight
                  className="absolute opacity-50 right-2 top-2.5 h-7 w-7 sm:right-3 sm:top-3 sm:h-10 sm:w-10"
                />
              </button>
            </div>
            <label
              htmlFor="dropzone-file"
              className="flex flex-col items-center justify-center w-full h-full rounded-lg cursor-pointer bg-gray-50 hover:bg-gray-100"
            >
              <div className="flex flex-col items-center justify-center pt-5 pb-6">
                <Cloud className="h-6 w-6 text-zinc-500 mb-2" />
                <p className="mb-2 text-sm text-zinc-700">
                  <span className="font-semibold">Click to upload</span> or drag
                  and drop
                </p>
                <p className="text-xs text-zinc-500">
                  MP4 (up to {MAX_UPLOAD_MB}MB)
                </p>
              </div>

              {acceptedFiles && acceptedFiles[0] ? (
                <div className="max-w-xs bg-white flex items-center rounded-md overflow-hidden outline outline-[1px] outline-zinc-200 divide-x divide-zinc-200">
                  <div className="px-3 py-2 h-full grid place-items-center">
                    <File className="h-4 w-4 text-blue-500" />
                  </div>
                  <div className="px-3 py-2 h-full text-sm truncate">
                    {acceptedFiles[0].name}
                  </div>
                </div>
              ) : null}

              {isUploading ? (
                <div className="w-full mt-4 max-w-xs mx-auto">
                  <Progress
                    indicatorColor={
                      uploadProgress === 100 ? 'bg-green-500' : ''
                    }
                    value={uploadProgress}
                    className="h-1 w-full bg-zinc-200"
                  />
                  {uploadProgress === 100 ? (
                    <div className="flex gap-1 items-center justify-center text-sm text-zinc-700 text-center pt-2">
                      <Loader2 className="h-3 w-3 animate-spin" />
                      Processing...
                    </div>
                  ) : null}
                </div>
              ) : null}

              <input
                {...getInputProps()}
                type="file"
                id="dropzone-file"
                className="hidden"
              />
            </label>
          </div>
        </div>
      )}
    </Dropzone>
  );
};

const UploadButton = () => {
  const [isOpen, setIsOpen] = useState<boolean>(false);

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(v) => {
        if (!v) {
          setIsOpen(v);
        }
      }}
    >
      <DialogTrigger onClick={() => setIsOpen(true)} asChild>
        <Button>Upload MP4</Button>
      </DialogTrigger>

      <DialogContent>
        <DialogTitle className="sr-only">Upload MP4</DialogTitle>
        <UploadDropzone />
      </DialogContent>
    </Dialog>
  );
};

export default UploadButton;