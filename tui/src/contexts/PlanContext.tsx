import { createContext, use, useReducer, type ReactNode } from "react";

export interface PlanTask {
  description: string;
  status: "pending" | "running" | "completed" | "failed";
  result?: string;
}

export interface PlanState {
  name: string | null;
  tasks: PlanTask[];
  notepadContent: string;
  createdAt: string | null;
}

export const INITIAL_STATE: PlanState = {
  name: null,
  tasks: [],
  notepadContent: "",
  createdAt: null,
};

export type PlanAction =
  | {
      type: "SET_PLAN";
      plan: { name: string; tasks: PlanTask[]; createdAt: string };
    }
  | { type: "UPDATE_TASK"; index: number; updates: Partial<PlanTask> }
  | { type: "SET_NOTEPAD"; content: string }
  | { type: "RESET_PLAN" };

export function planReducer(state: PlanState, action: PlanAction): PlanState {
  switch (action.type) {
    case "SET_PLAN":
      return {
        ...state,
        name: action.plan.name,
        tasks: action.plan.tasks,
        createdAt: action.plan.createdAt,
      };

    case "UPDATE_TASK":
      return {
        ...state,
        tasks: state.tasks.map((task, i) =>
          i === action.index ? { ...task, ...action.updates } : task
        ),
      };

    case "SET_NOTEPAD":
      return { ...state, notepadContent: action.content };

    case "RESET_PLAN":
      return INITIAL_STATE;

    default:
      return state;
  }
}

export const PlanContext = createContext<{
  state: PlanState;
  dispatch: React.Dispatch<PlanAction>;
} | null>(null);

export function PlanProvider({ children }: { children: ReactNode }): ReactNode {
  const [state, dispatch] = useReducer(planReducer, INITIAL_STATE);
  return <PlanContext value={{ state, dispatch }}>{children}</PlanContext>;
}

export function usePlan() {
  const context = use(PlanContext);
  if (!context) throw new Error("usePlan must be used within PlanProvider");
  return context;
}
