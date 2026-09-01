/**
 * 后端 API 类型定义（M3 骨架）。
 * 字段以任务描述中的 API 契约为准；M4 联调时如与实际响应有出入，只改此处。
 */

// ---------- 公共视图 ----------

export interface PlayerInfo {
  uid: string
  name: string
  is_host: boolean
  is_away: boolean
  has_submitted: boolean
  action_version: number | null
  joined_at: string
}

export interface CharacterEntry {
  uid: string
  name: string
  /** 角色卡 JSON（schema: coc7-character/v1） */
  data: Record<string, unknown>
}

export interface GameView {
  game_key: string
  name: string
  rule: string
  module_id: string | null
  world_summary: string | null
  phase: string
  round: number
  current_scene: string | null
  /** 每局 LLM 输出上限（NULL=用 config 默认；房主可经 /llm-limit 调整） */
  max_tokens: number | null
  created_at: string
  players: PlayerInfo[]
  characters: CharacterEntry[]
}

// ---------- REST 请求 / 响应 ----------

export interface CreateGamePayload {
  name: string
  rule?: string
  module_id?: string
  world_summary?: string
  host_name?: string
  /** M5.1：可选访问密码 */
  password?: string
}

export interface CreateGameResponse {
  game_key: string
  host_uid: string
  host_token: string
  game: GameView
  /** M5.1：邀请凭证（房主分享给其他玩家的加入码） */
  invite_token: string
}

export interface GetGameResponse {
  game: GameView
}

export interface JoinGameResponse {
  player: PlayerInfo
  player_token: string
}

/** 加入请求体（M5.1）：邀请凭证走 X-Join-Token 头，密码可选 */
export interface JoinGamePayload {
  name: string
  password?: string
}

/** 建卡请求：引擎自动生成（auto）或直传角色卡 JSON（character）二选一 */
export type BuildCharacterPayload =
  | { action: 'auto'; name?: string }
  | { character: Record<string, unknown>; name?: string }

export interface CharacterResponse {
  character: Record<string, unknown>
}

export interface GetCharacterResponse {
  character: Record<string, unknown>
}

export interface CharactersResponse {
  characters: CharacterEntry[]
}

export interface SubmitActionResponse {
  accepted: boolean
  round: number
  action_version: number
  /** M4：单人/全员就绪时自动推进 */
  auto_advanced?: boolean
}

export interface RollResult {
  ok: boolean
  kind: string
  by?: string
  why?: string
  expr: string
  n?: number
  m?: number
  k?: number
  rolls: number[]
  total: number
}

export interface RollResponse {
  result: RollResult
}

export interface AuditResponse {
  audit: unknown[]
}

export interface AdvanceResponse {
  triggered: boolean
  round: number
}

export interface HealthResponse {
  status: string
}

// ---------- 模组 ----------

export interface ModuleInfo {
  schema: string
  id: string
  number: number
  name: string
  cn: string
  author: string
  system: string
  players: string
  duration: string
  recommended_skills: string[]
  tags: string[]
  summary: string
  background: string
  scene_flow: string[]
  [key: string]: unknown
}

export interface ModulesResponse {
  modules: ModuleInfo[]
  count: number
}

export interface SceneInfo {
  id: string
  name: string
  location: string
  summary: string
  checks: unknown[]
  clues: unknown[]
  npcs: unknown[]
  handouts: unknown[]
  next: string[] | string | null
}

export interface ModuleScenesResponse {
  scene_flow: string[]
  scenes: SceneInfo[]
}

export interface PregensResponse {
  module_id: string
  pregens: Record<string, unknown>[]
}

// ---------- 叙事流消息（M4） ----------

export interface MessageRecord {
  id: number
  round: number
  kind: string
  seq: number
  payload: Record<string, unknown>
  created_at: number
}

export interface MessagesResponse {
  messages: MessageRecord[]
  count: number
}

// ---------- SSE 事件 ----------

export interface RoundStartedEvent {
  round: number
  phase: string
}

export interface ActionReceivedEvent {
  uid: string
  name: string
  round: number
  action_version: number
}

/** 骰果事件：RollResult 字段 + uid/name/round */
export interface DiceResultEvent {
  uid: string
  name: string
  round: number
  ok: boolean
  kind: string
  by?: string
  why?: string
  expr: string
  n?: number
  m?: number
  k?: number
  rolls: number[]
  total: number
}

export interface NarrationEvent {
  round: number
  text: string
}

/** 定向感知：只应送达 to 指定的 uid（后端依赖 X-Player-Token 头绑定） */
export interface PerceptionEvent {
  to: string
  text: string
}

export interface TurnAdvancedEvent {
  round: number
  phase: string
}

export interface CharacterReadyEvent {
  uid: string
  name: string
}

/** 场景切换事件（M4）：scene 为场景摘要，handouts 为附件文件名列表 */
export interface SceneChangedEvent {
  scene: {
    id: string
    name: string
    location: string
    summary: string
  }
  handouts: string[]
}

/** 附件事件（M4）：file 为附件相对路径（handouts/ 下） */
export interface HandoutEvent {
  file: string
}

/** 玩家暂离/回归事件（M5.2） */
export interface PlayerStatusEvent {
  uid: string
  is_away: boolean
}

/** 玩家被移除事件（M5.4 房主踢人） */
export interface PlayerRemovedEvent {
  uid: string
}

/** 局内聊天事件（M7 额外任务）：expr/total/rolls 存在时表示联掷分享 */
export interface ChatEvent {
  uid: string
  name: string
  text: string
  expr?: string
  total?: number
  rolls?: number[]
  ts?: number
}

/** LLM 输出被 max_tokens 截断事件：提示房主调高上限（只含提示文本，绝不含思考内容） */
export interface LlmLimitHitEvent {
  round: number
  stage: string
  text: string
  max_tokens: number
  suggested: number
}

/** 房主调整本局 LLM 输出上限事件 */
export interface LlmLimitChangedEvent {
  max_tokens: number
}

/** 事件名 → 事件 data 的映射（SSE 各事件统一回调 onEvent(name, data)） */
export interface SseEventMap {
  round_started: RoundStartedEvent
  action_received: ActionReceivedEvent
  dice_result: DiceResultEvent
  narration: NarrationEvent
  state_changed: Record<string, unknown>
  perception: PerceptionEvent
  turn_advanced: TurnAdvancedEvent
  character_ready: CharacterReadyEvent
  scene_changed: SceneChangedEvent
  handout: HandoutEvent
  player_status: PlayerStatusEvent
  player_removed: PlayerRemovedEvent
  chat: ChatEvent
  llm_limit_hit: LlmLimitHitEvent
  llm_limit_changed: LlmLimitChangedEvent
}

export type SseEventName = keyof SseEventMap
