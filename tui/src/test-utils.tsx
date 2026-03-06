import { render as inkRender } from "ink-testing-library";
import type { ReactElement } from "react";

export function renderApp(component: ReactElement): ReturnType<typeof inkRender> {
  return inkRender(component);
}

/**
 * Wait for specific text to appear in rendered output.
 */
export async function waitForText(
  instance: ReturnType<typeof inkRender>,
  text: string,
  timeout = 2000,
): Promise<void> {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    if (instance.lastFrame()?.includes(text)) {
      return;
    }
    await new Promise((r) => setTimeout(r, 50));
  }
  throw new Error(
    `Text "${text}" not found within ${timeout}ms. Last frame: ${instance.lastFrame()}`,
  );
}
