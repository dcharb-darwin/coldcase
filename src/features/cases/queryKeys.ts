export const caseKeys = {
  all: ["cases"] as const,
  list: () => ["cases", "list"] as const,
  detail: (id: string) => ["cases", "detail", id] as const,
  conversations: (id: string) => ["cases", id, "conversations"] as const,
  reports: (id: string) => ["cases", id, "reports"] as const,
  auditSummary: (id: string) => ["cases", id, "audit-summary"] as const,
};

export const conversationKeys = {
  messages: (id: string) => ["conversations", id, "messages"] as const,
};

export const reportKeys = {
  detail: (id: string) => ["reports", id] as const,
  chain: (id: string) => ["reports", id, "chain"] as const,
};
