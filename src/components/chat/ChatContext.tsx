import { ReactNode, createContext, useRef, useState } from 'react';
import { useToast } from '../ui/use-toast';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { invoke } from '@tauri-apps/api/core';
import { isTauri } from '@/lib/runtime';

type StreamResponse = {
  addMessage: () => void;
  message: string;
  handleInputChange: (event: React.ChangeEvent<HTMLTextAreaElement>) => void;
  isLoading: boolean;
};

export const ChatContext = createContext<StreamResponse>({
  addMessage: () => {},
  message: '',
  handleInputChange: () => {},
  isLoading: false,
});

interface Props {
  fileId: string;
  children: ReactNode;
}

interface Message {
  id: string;
  text: string;
  isUserMessage: boolean;
  createdAt: string;
}

// Query key factory
const getFileMessagesQueryKey = (fileId: string) => ['messages', fileId];

export const ChatContextProvider = ({ fileId, children }: Props) => {
  const [message, setMessage] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const { toast } = useToast();
  const backupMessage = useRef('');
  const queryClient = useQueryClient();

  const { mutate: sendMessage } = useMutation({
    mutationFn: async ({ message }: { message: string }) => {
      // Fully local mode: always route through Tauri backend
      return await invoke<string>('send_message', { fileId, message });
    },

    onMutate: async ({ message }) => {
      backupMessage.current = message;
      setMessage('');

      const queryKey = getFileMessagesQueryKey(fileId);
      queryClient.setQueryData(queryKey, (old: any) => {
        const now = new Date().toISOString();
        if (!old || !old.pages || old.pages.length === 0) {
          return {
            pages: [
              {
                messages: [
                  {
                    createdAt: now,
                    id: crypto.randomUUID(),
                    text: message,
                    isUserMessage: true,
                  },
                ],
              },
            ],
            pageParams: [],
          };
        }
        let newPages = [...old.pages];
        // Append to the end to keep chronological ASC order (top->bottom oldest->newest)
        const lastPageIndex = newPages.length - 1;
        const lastPage = newPages[lastPageIndex];
        const updatedLastPage = {
          ...lastPage,
          messages: [
            ...lastPage.messages,
            {
              createdAt: now,
              id: crypto.randomUUID(),
              text: message,
              isUserMessage: true,
            },
          ],
        };
        newPages[lastPageIndex] = updatedLastPage;
        return { ...old, pages: newPages };
      });

      setIsLoading(true);
      return {};
    },

    onSuccess: async (response) => {
      setIsLoading(false);
      if (!response) {
        return toast({
          title: 'There was a problem sending this message',
          description: 'Please refresh this page and try again',
          variant: 'destructive',
        });
      }
      const queryKey = getFileMessagesQueryKey(fileId);
      queryClient.setQueryData(queryKey, (old: any) => {
        const now = new Date().toISOString();
        if (!old || !old.pages || old.pages.length === 0) {
          return {
            pages: [
              {
                messages: [
                  {
                    createdAt: now,
                    id: 'ai-response',
                    text: response,
                    isUserMessage: false,
                  },
                ],
              },
            ],
            pageParams: [],
          };
        }
        // Append AI response immediately after the user's message (i.e., at the end)
        let newPages = [...old.pages];
        const lastPageIndex = newPages.length - 1;
        const lastPage = newPages[lastPageIndex];
        const updatedLastPage = {
          ...lastPage,
          messages: [
            ...lastPage.messages,
            {
              createdAt: now,
              id: 'ai-response',
              text: response,
              isUserMessage: false,
            },
          ],
        };
        newPages[lastPageIndex] = updatedLastPage;
        return { ...old, pages: newPages };
      });
    },

    onError: () => {
      setMessage(backupMessage.current);
      toast({
        title: 'Error sending message',
        description: 'Please try again',
        variant: 'destructive',
      });
    },

    onSettled: async () => {
      setIsLoading(false);
      await queryClient.invalidateQueries({
        queryKey: getFileMessagesQueryKey(fileId),
      });
    },
  });

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setMessage(e.target.value);
  };

  const addMessage = () => sendMessage({ message });

  return (
    <ChatContext.Provider
      value={{
        addMessage,
        message,
        handleInputChange,
        isLoading,
      }}
    >
      {children}
    </ChatContext.Provider>
  );
};