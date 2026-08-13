"""Realistic MCP server source fixtures, one per declaration idiom.

Hand-written to mirror the shapes found in real servers. These are the
ground truth against which extractor recall is measured -- see
docs/06-dataset-plan.md section 4. An extractor with unknown recall makes
the whole ecosystem measurement uninterpretable, so recall is measured,
not assumed.
"""

FASTMCP_PY = '''
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("bank")

@mcp.tool()
def check_balance() -> float:
    """Return the current account balance."""
    return _balance

@mcp.tool()
def transfer_money(recipient: str, amount: float, memo: str = "") -> dict:
    """Transfer the specified amount to the specified recipient."""
    return _do_transfer(recipient, amount, memo)

@mcp.tool()
async def list_transactions(limit: int = 20) -> list:
    """List recent transactions on the account."""
    return _ledger[:limit]

def not_a_tool(x):
    """This should not be extracted."""
    return x
'''

LOWLEVEL_PY = '''
import mcp.types as types
from mcp.server import Server

server = Server("files")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="read_file",
            description="Read the contents of a file at the given path.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                },
                "required": ["path"],
            },
        ),
        types.Tool(
            name="write_file",
            description="Write content to a file at the given path.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
            },
        ),
    ]
'''

TS_SERVER_TOOL = '''
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";

const server = new McpServer({ name: "mail", version: "1.0.0" });

server.tool(
  "send_email",
  "Send an email to the specified recipient.",
  {
    to: z.string().email(),
    subject: z.string(),
    body: z.string(),
  },
  async ({ to, subject, body }) => {
    return { content: [{ type: "text", text: "sent" }] };
  }
);

server.tool(
  "list_inbox",
  "List messages currently in the inbox.",
  {
    limit: z.number().optional(),
  },
  async ({ limit }) => {
    return { content: [] };
  }
);
'''

TS_OBJECT_LITERAL = '''
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "send_webhook",
      description: "Post a payload to a configured webhook URL.",
      inputSchema: {
        type: "object",
        properties: { url: { type: "string" }, payload: { type: "object" } },
      },
    },
  ],
}));
'''

JSON_MANIFEST = '''
{
  "tools": [
    {
      "name": "search_docs",
      "description": "Search the documentation index.",
      "inputSchema": {
        "type": "object",
        "properties": { "query": { "type": "string" }, "top_k": { "type": "number" } }
      }
    },
    {
      "name": "log_event",
      "description": "Append an event to the audit log.",
      "inputSchema": { "type": "object", "properties": { "message": { "type": "string" } } }
    }
  ]
}
'''

# (source, path, expected tool names)
FIXTURES = [
    (FASTMCP_PY, "bank_server.py",
     {"check_balance", "transfer_money", "list_transactions"}),
    (LOWLEVEL_PY, "file_server.py",
     {"read_file", "write_file"}),
    (TS_SERVER_TOOL, "mail_server.ts",
     {"send_email", "list_inbox"}),
    (TS_OBJECT_LITERAL, "hook_server.ts",
     {"send_webhook"}),
    (JSON_MANIFEST, "tools.json",
     {"search_docs", "log_event"}),
]
