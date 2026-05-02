/**
 * Mutation to reply to a pull request review thread.
 * Used by the `reply` command.
 *
 * Variables: $threadId, $body
 */
export const ADD_REPLY_MUTATION = `
mutation($threadId: ID!, $body: String!) {
  addPullRequestReviewThreadReply(input: {
    pullRequestReviewThreadId: $threadId,
    body: $body
  }) {
    comment {
      id
    }
  }
}
`;

/**
 * Mutation to resolve a review thread.
 * Used by the `resolve` command.
 *
 * Variables: $threadId
 */
export const RESOLVE_THREAD_MUTATION = `
mutation($threadId: ID!) {
  resolveReviewThread(input: {
    threadId: $threadId
  }) {
    thread {
      id
      isResolved
    }
  }
}
`;

/**
 * Mutation to unresolve a review thread.
 * Used by the `unresolve` command.
 *
 * Variables: $threadId
 */
export const UNRESOLVE_THREAD_MUTATION = `
mutation($threadId: ID!) {
  unresolveReviewThread(input: {
    threadId: $threadId
  }) {
    thread {
      id
      isResolved
    }
  }
}
`;
