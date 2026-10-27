import { Component, type ErrorInfo, type ReactNode } from "react";

import { AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";

export class EditorErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Editor failed", error, info.componentStack);
  }
  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div
        className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center"
        role="alert"
      >
        <AlertTriangle className="size-7 text-primary" />
        <h1 className="text-base font-semibold">The editor could not render this workspace</h1>
        <p className="max-w-sm text-sm text-muted-foreground">
          Reload the editor to recover. Changes in this session have not been saved.
        </p>
        <Button onClick={() => window.location.reload()}>Reload editor</Button>
      </div>
    );
  }
}
