import { ReactElement } from 'react';

export type Message = {
  id: string;
  text: string;
  isUserMessage: boolean;
  createdAt: string;
};

// Extended message type that allows JSX.Element for loading states
type OmitText = Omit<Message, 'text'>;

type ExtendedText = {
  text: string | ReactElement;
};

export type ExtendedMessage = OmitText & ExtendedText;