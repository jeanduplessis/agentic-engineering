import { graphql } from "../gh";
import { THREADS_QUERY } from "../graphql/queries";
import type { ParsedArgs } from "../utils";
import { resolvePR, outputJSON, exitWithError } from "../utils";
import type { ThreadSummary, GQLReviewThread, GQLPageInfo } from "../types";

interface ThreadsQueryResponse {
  repository: {
    pullRequest: {
      reviewThreads: {
        nodes: GQLReviewThread[];
        pageInfo: GQLPageInfo;
      };
    };
  };
}

export function threadsCommand(args: ParsedArgs): void {
  try {
    const { owner, repo, number } = resolvePR(args);

    const allThreads: GQLReviewThread[] = [];
    let cursor: string | undefined;

    do {
      const variables: Record<string, string | number | boolean> = { owner, repo, number };
      if (cursor) {
        variables.cursor = cursor;
      }

      const data = graphql<ThreadsQueryResponse>(THREADS_QUERY, variables);
      const { nodes, pageInfo } = data.repository.pullRequest.reviewThreads;

      allThreads.push(...nodes);

      if (pageInfo.hasNextPage && pageInfo.endCursor) {
        cursor = pageInfo.endCursor;
      } else {
        cursor = undefined;
      }
    } while (cursor);

    let summaries: ThreadSummary[] = allThreads.map((thread) => ({
      threadId: thread.id,
      isResolved: thread.isResolved,
      path: thread.path,
      ...(thread.line != null ? { line: thread.line } : {}),
      isOutdated: thread.isOutdated,
    }));

    if (args.flags["unresolved"] !== undefined) {
      summaries = summaries.filter((t) => t.isResolved === false);
    }

    outputJSON(summaries);
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    exitWithError(message);
  }
}
