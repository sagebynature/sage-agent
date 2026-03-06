export interface TruncatedDelegationChain {
  visible: string[];
  hiddenCount: number;
}

export function formatHiddenDelegationMessage(hiddenCount: number): string {
  return `... ${hiddenCount} more levels`;
}

export function truncateDelegationChain(
  chain: string[],
  maxDepth = 5,
): TruncatedDelegationChain {
  if (chain.length <= maxDepth) {
    return {
      visible: chain,
      hiddenCount: 0,
    };
  }

  const hiddenCount = chain.length - maxDepth;
  return {
    visible: chain.slice(0, maxDepth),
    hiddenCount,
  };
}
