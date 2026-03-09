#!/usr/bin/env node
import { render } from "ink";
import { App } from "./App.js";
import { buildClientOptions } from "./cli.js";

render(<App clientOptions={buildClientOptions(process.argv.slice(2))} />, {
  exitOnCtrlC: false,
});
