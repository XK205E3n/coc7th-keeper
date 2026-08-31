# -*- coding: utf-8 -*-
"""AI 守密人包（M2）：llm / prompts / adjudicate / narrate / pipeline / simulate。

架构（两阶段 + 服务端固定骰果）：
  行动 + 场景 + kp-notes → adjudicate（裁判，输出 dice_checks JSON）
  → 服务端引擎掷骰（固定骰果）→ narrate（叙事，输出 narrative + state_changes）
  → state_apply（校验落库）→ 广播
"""
