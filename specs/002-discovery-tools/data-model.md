# Data Model: Discovery Tools

Additions to [spec 001's data model](../001-bluesky-mcp-server/data-model.md). The server still
stores nothing of its own; these are result shapes.

| Entity | Fields |
| --- | --- |
| **FeedView** | `uri`, `url` (bsky.app link), `name`, `creator_handle`, `description`, `like_count`, `is_online`, `is_valid` (the last two only from `get_feed_info`) |
| **FeedPage** | `feeds: list[FeedView]`, `cursor` |
| **ListInfo** | `uri`, `url`, `name`, `purpose` (`curatelist` / `modlist` / `referencelist`), `creator_handle`, `description`, `member_count` |
| **ListPage** | `lists: list[ListInfo]`, `cursor` |
| **ListDetail** | `list: ListInfo`, `members: list[ProfileView]`, `cursor` |
| **StarterPackInfo** | `uri`, `url`, `name`, `creator_handle`, `description`, `joined_week_count`, `joined_all_time_count` |
| **StarterPackPage** | `starter_packs: list[StarterPackInfo]`, `cursor` |
| **StarterPackDetail** | `starter_pack: StarterPackInfo`, `list_url`, `members: list[ProfileView]`, `cursor` |
| **TrendingTopic** | `topic`, `display_name`, `description`, `url` (absolute bsky.app link) |
| **TrendingPage** | `topics: list[TrendingTopic]` |
| **ListMembershipResult** | `actor`, `status` (`added` / `already_member` / `not_found`) |
| **DeletedList** | `deleted`, `url`, `name`, `members_removed` |

Validation rules: list name 1–64 characters, description at most 3000 (from the
`app.bsky.graph.list` record model); `add_to_list` takes 1–25 accounts per call; trending `limit`
1–25.
