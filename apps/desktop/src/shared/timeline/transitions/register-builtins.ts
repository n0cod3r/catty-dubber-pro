/**
 * Register Built-in Transitions
 *
 * Calls all renderer registration functions to populate the global registry.
 * Called once at module load time.
 */

import { transitionRegistry } from "./registry";
import {
  registerBasicTransitions,
  registerFlipTransitions,
  registerGpuTransitions,
  registerIrisTransitions,
  registerMaskTransitions,
  registerMotionTransitions,
  registerShapeTransitions,
  registerSlideTransitions,
  registerWipeTransitions,
} from "./renderers";

let registered = false;

export function registerBuiltinTransitions(): void {
  if (registered) return;
  registered = true;

  registerBasicTransitions(transitionRegistry);
  registerMotionTransitions(transitionRegistry);
  registerWipeTransitions(transitionRegistry);
  registerSlideTransitions(transitionRegistry);
  registerFlipTransitions(transitionRegistry);
  registerMaskTransitions(transitionRegistry);
  registerIrisTransitions(transitionRegistry);
  registerShapeTransitions(transitionRegistry);
  registerGpuTransitions(transitionRegistry);
}
