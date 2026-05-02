import { graphql } from "../gh";
import { RESOLVE_THREAD_MUTATION } from "../graphql/mutations";
import type { ParsedArgs } from "../utils";
import { resolvePR, outputJSON, exitWithError } from "../utils";
import type { ThreadMutationResult } from "../types";

interface ResolveThreadResponse {
  resolveReviewThread: {
    thread: {
      id: string;
      isResolved: boolean;
    };
  };
}

export function resolveCommand(args: ParsedArgs): void {
  try {
    resolvePR(args);

    const threadId = args.flags["thread-id"];
    if (!threadId) {
      exitWithError("--thread-id is required");
    }

    const response = graphql<ResolveThreadResponse>(RESOLVE_THREAD_MUTATION, { threadId });

    const result: ThreadMutationResult = {
      thread_node_id: response.resolveReviewThread.thread.id,
      is_resolved: response.resolveReviewThread.thread.isResolved,
    };

    outputJSON(result);
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    exitWithError(message);
  }
}
