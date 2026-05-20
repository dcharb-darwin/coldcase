#!/bin/bash
# Cold Case — end-to-end smoke covering this session's compliance work.
#
# Asserts:
#   1. Preflight returns ready=true with all 6 checks green.
#   2. A case can be created, a conversation started, a message sent.
#   3. The message can be promoted to a report (becomes the §13663(b) first draft).
#   4. PATCH /messages/{first-draft-id} returns 403 and emits FIRST_DRAFT_MUTATION_BLOCKED.
#   5. The report can be signed.
#   6. Manual retention sweep (dry-run) returns a structured report.
#   7. The new audit-event types appear when expected.

set -u

API=http://localhost:7787/launchpad/coldcase/api
FAILED=0
pass() { echo "  ✅ $1"; }
fail() { echo "  ❌ $1"; FAILED=$((FAILED+1)); }

j() { python3 -c "import sys,json; d=json.load(sys.stdin); print(d$1)" 2>/dev/null; }

echo
echo "── 1. Compliance preflight"
PRE=$(curl -s "$API/admin/compliance/preflight")
READY=$(echo "$PRE" | j "['ready']")
if [ "$READY" = "True" ]; then pass "preflight ready=true"; else fail "preflight ready=$READY"; fi
N_CHECKS=$(echo "$PRE" | j "['checks'].__len__()")
# 7 checks today: auth bypass, llm model, agency letterhead, retention scheduler,
# vendor scope, policy template, audit chain integrity. Update when adding more.
[ "$N_CHECKS" -ge "7" ] && pass "$N_CHECKS preflight checks present" || fail "expected ≥7 checks, got $N_CHECKS"

echo
echo "── 2. Create case + conversation + message"
CASE_NUM="SMOKE-$(date +%s)"
CASE=$(curl -sX POST "$API/cases" -H 'Content-Type: application/json' \
  -d "{\"case_number\":\"$CASE_NUM\",\"title\":\"e2e smoke\",\"classification\":\"other\"}")
CASE_ID=$(echo "$CASE" | j "['id']")
[ -n "$CASE_ID" ] && pass "case created id=$CASE_ID" || { fail "case create: $CASE"; exit 1; }

CONV=$(curl -sX POST "$API/cases/$CASE_ID/conversations" -H 'Content-Type: application/json' -d '{"title":"smoke"}')
CONV_ID=$(echo "$CONV" | j "['id']")
[ -n "$CONV_ID" ] && pass "conversation id=$CONV_ID" || { fail "conv: $CONV"; exit 1; }

MSG=$(curl -sX POST "$API/conversations/$CONV_ID/messages" -H 'Content-Type: application/json' \
  -d '{"content":"Summarize the case file."}')
USER_MSG_ID=$(echo "$MSG" | j "['user_message']['id']")
ASSISTANT_MSG_ID=$(echo "$MSG" | j "['assistant_message']['id']")
[ -n "$ASSISTANT_MSG_ID" ] && pass "assistant message id=$ASSISTANT_MSG_ID" || { fail "msg: $MSG"; exit 1; }

echo
echo "── 3. Promote → first AI draft"
REPORT=$(curl -sX POST "$API/reports/promote" -H 'Content-Type: application/json' \
  -d "{\"title\":\"Smoke report\",\"message_id\":\"$ASSISTANT_MSG_ID\"}")
REPORT_ID=$(echo "$REPORT" | j "['id']")
FD_ID=$(echo "$REPORT" | j "['first_ai_draft_message_id']")
[ "$FD_ID" = "$ASSISTANT_MSG_ID" ] && pass "first_ai_draft_message_id locked" || fail "first-draft id mismatch ($FD_ID vs $ASSISTANT_MSG_ID)"

echo
echo "── 4. First-draft mutation deny path"
DENY_CODE=$(curl -s -o /tmp/cc_deny.json -w "%{http_code}" \
  -X PATCH "$API/messages/$ASSISTANT_MSG_ID" \
  -H 'Content-Type: application/json' -d '{"content":"officer cannot rewrite this"}')
[ "$DENY_CODE" = "403" ] && pass "PATCH on first-draft returns 403" || fail "expected 403, got $DENY_CODE"
grep -q "§13663(b)" /tmp/cc_deny.json && pass "403 body cites §13663(b)" || fail "403 body missing statute cite"

# Non-first-draft (the user message) should 405, not 403.
USER_PATCH_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -X PATCH "$API/messages/$USER_MSG_ID" \
  -H 'Content-Type: application/json' -d '{"content":"x"}')
[ "$USER_PATCH_CODE" = "405" ] && pass "PATCH on user msg returns 405" || fail "expected 405 on non-first-draft, got $USER_PATCH_CODE"

# Confirm the FIRST_DRAFT_MUTATION_BLOCKED audit event landed.
sleep 1
AUDIT=$(curl -s "$API/audit/events?event_type=first_draft.mutation_blocked&limit=5")
HITS=$(echo "$AUDIT" | python3 -c "import sys,json; d=json.load(sys.stdin); events=d.get('events',d) if isinstance(d,dict) else d; print(sum(1 for e in events if e.get('event_type')=='first_draft.mutation_blocked'))" 2>/dev/null)
[ "${HITS:-0}" -ge 1 ] && pass "FIRST_DRAFT_MUTATION_BLOCKED audit event emitted ($HITS hits)" || fail "no audit event found (got: $(echo "$AUDIT" | head -c 200))"

echo
echo "── 5. Sign the report"
SIGN_CODE=$(curl -s -o /tmp/cc_sign.json -w "%{http_code}" \
  -X POST "$API/reports/$REPORT_ID/sign" \
  -H 'Content-Type: application/json' -d '{"badge_number":"4242"}')
[ "$SIGN_CODE" = "200" ] && pass "report signed (HTTP 200)" || fail "sign failed code=$SIGN_CODE body=$(cat /tmp/cc_sign.json)"

echo
echo "── 6. Manual retention sweep (dry-run)"
SWEEP=$(curl -sX POST "$API/admin/retention/sweep?apply=false")
INSPECTED=$(echo "$SWEEP" | j "['inspected']")
[ -n "$INSPECTED" ] && pass "sweep ran, inspected=$INSPECTED" || fail "sweep response: $SWEEP"

echo
echo "── Result"
if [ "$FAILED" -eq 0 ]; then
  echo "  🟢 all assertions passed"
  exit 0
else
  echo "  🔴 $FAILED assertion(s) failed"
  exit 1
fi
