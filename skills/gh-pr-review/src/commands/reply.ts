import { graphql } from "../gh";
import { ADD_REPLY_MUTATION } from "../graphql/mutations";
import type { ParsedArgs } from "../utils";
import { resolvePR, outputJSON, exitWithError } from "../utils";
import type { ReplyMinimal } from "../types";

interface AddReplyResponse {
  addPullRequestReviewThreadReply: {
    comment: {
      id: string;
    };
  };
}

export function replyCommand(args: ParsedArgs): void {
  try {
    resolvePR(args);

    const threadId = args.flags["thread-id"];
    const body = args.flags["body"];

    if (!threadId) {
      exitWithError("Missing required flag: --thread-id");
    }

    if (!body) {
      exitWithError("Missing required flag: --body");
    }

    const response = graphql<AddReplyResponse>(ADD_REPLY_MUTATION, { threadId, body });

    const result: ReplyMinimal = {
      comment_node_id: response.addPullRequestReviewThreadReply.comment.id,
    };

    outputJSON(result);
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Unknown error";
    exitWithError(message);
  }
}
