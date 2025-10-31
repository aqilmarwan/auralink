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
        if (!old) return { pages: [], pageParams: [] };
        let newPages = [...old.pages];
        let latestPage = newPages[0]!;
        latestPage.messages = [
          {
            createdAt: new Date().toISOString(),
            id: crypto.randomUUID(),
            text: message,
            isUserMessage: true,
          },
          ...latestPage.messages,
        ];
        newPages[0] = latestPage;
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
        if (!old) return { pages: [], pageParams: [] };
        const isAiResponseCreated = old.pages.some((page: { messages: Message[] }) =>
          page.messages.some((message: Message) => message.id === 'ai-response')
        );
        let updatedPages = old.pages.map((page: { messages: Message[] }) => {
          if (page === old.pages[0]) {
            let updatedMessages;
            if (!isAiResponseCreated) {
              updatedMessages = [
                {
                  createdAt: new Date().toISOString(),
                  id: 'ai-response',
                  text: response,
                  isUserMessage: false,
                },
                ...page.messages,
              ];
            } else {
              updatedMessages = page.messages.map((message: Message) =>
                message.id === 'ai-response' ? { ...message, text: response } : message
              );
            }
            return { ...page, messages: updatedMessages };
          }
          return page;
        });
        return { ...old, pages: updatedPages };
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