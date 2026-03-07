import { createContext, use, useReducer, type ReactNode } from "react";
import { blockReducer, INITIAL_BLOCK_STATE, type BlockState, type BlockAction } from "./blockReducer.js";

const BlockContext = createContext<{
  state: BlockState;
  dispatch: React.Dispatch<BlockAction>;
} | null>(null);

export function BlockProvider({ children }: { children: ReactNode }): ReactNode {
  const [state, dispatch] = useReducer(blockReducer, INITIAL_BLOCK_STATE);
  return <BlockContext value={{ state, dispatch }}>{children}</BlockContext>;
}

export function useBlocks() {
  const context = use(BlockContext);
  if (!context) throw new Error("useBlocks must be used within BlockProvider");
  return context;
}
