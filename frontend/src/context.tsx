import { createContext, useContext } from "react";
import type { Row, User } from "./types";
export type Workspace = {
  user: User;
  bots: Row[];
  kbs: Row[];
  models: Row[];
  providers: Row[];
  embeddings: Row[];
  reload: () => Promise<void>;
  notify: (text: string) => void;
};
export const Context = createContext<Workspace>(null!);
export const useWorkspace = () => useContext(Context);
