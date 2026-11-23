# Merge AI Agents

Merge AI now includes a specialist Agents hub with built-in agents and custom agents.

## Built-in agents
- Researcher
- Coding Engineer
- Study Tutor
- Writing Partner
- Data Analyst
- Science Fair Mentor

Each agent has its own identity, instructions and saved conversation threads. Agent chats use the existing `ma2_chats` storage, so they don't need a new chat-history column.

## Save custom agents across devices

1. Open your Supabase project.
2. Go to **SQL Editor**.
3. Run the SQL in `supabase_agents.sql`.
4. Sign in to Merge AI with Google and refresh the app.

If the table is not configured, built-in agents continue to work and custom agents remain in the current browser session only.

## Scope

These are specialist conversational agents that use the existing Merge AI providers, Fast/Deep mode and web-search setting. They do not have independent cloud computers, autonomous background execution, external app access or approval workflows yet.
