// A request lease belongs to one project/episode generation. Resetting scope
// invalidates even an A → B → A request; old finally blocks cannot unlock B.
export function createDialogueSessionGuard() {
  let scope: string | null = null;
  let active: object | null = null;
  return {
    reset(nextScope: string | null) {
      scope = nextScope;
      active = null;
    },
    begin(expectedScope: string) {
      if (scope !== expectedScope || active) return null;
      active = {};
      return active;
    },
    isCurrent(ticket: object) {
      return active === ticket;
    },
    finish(ticket: object) {
      if (active !== ticket) return false;
      active = null;
      return true;
    },
  };
}
