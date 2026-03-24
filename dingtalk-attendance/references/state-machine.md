# 钉钉考勤状态机

## 意图

- `open`: 只进入考勤打卡页面
- `clock-in`: 进入考勤页后尝试打上班卡
- `clock-out`: 进入考勤页后尝试打下班卡
- `retry-local-install`: 重新尝试启用本地 OCR

## 提示词执行规则

- 用户提示词是 `上班打卡 / 打上班卡 / 下班打卡 / 打下班卡` 这类直接指令：
  - 视为 `auto_execute = true`
  - 导航到考勤页后可直接点击对应按钮
- 用户提示词只是打开页面、查看状态或不够直接：
  - 先导航和识别
  - 由上层再决定是否继续执行

## 页面优先级

1. 锁屏
2. 非钉钉页面
3. 钉钉首页
4. 工作台
5. 考勤页
6. 未知 WebView / 弹窗页

## 导航顺序

1. 检查设备连接
2. 唤醒并滑动解锁
3. 启动钉钉
4. 尝试关闭文字可识别弹窗
5. 尝试用模板匹配关闭无文字弹窗或点击返回 icon
6. 若当前可见“工作台”，进入工作台
7. 若当前可见“考勤打卡”，进入考勤页
8. 若已经在考勤页，进入打卡逻辑
9. 若仍无法判断，进入模型兜底

## 上班卡逻辑

- 出现 `上班打卡 / 上班卡 / 立即打卡 / 更新打卡`：
  - 若 `auto_execute = true`，点击
  - 否则返回可执行状态给上层
- 出现 `已打上班卡 / 今日上班已打卡 / 上班已打卡`：
  - 返回 `already_done`
- 其他情况：
  - 返回 `needs_model_input`

## 下班卡逻辑

- 出现 `下班打卡 / 下班卡 / 立即打卡 / 更新打卡`：
  - 若 `auto_execute = true`，点击
  - 否则返回可执行状态给上层
- 出现 `已打下班卡 / 今日下班已打卡 / 下班已打卡`：
  - 返回 `needs_confirmation`
- 其他情况：
  - 返回 `needs_model_input`

## 模型兜底规则

脚本返回 `needs_model_input` 后，当前模型只做一次判断并执行一个动作：

- 点关闭按钮
- 点暂不更新
- 点左上角返回
- 点工作台
- 点考勤打卡
- 点上班打卡
- 点下班打卡

模型给出动作后，优先通过 `model-action` 执行：

```bash
python3 scripts/run.py model-action --action tap-workbench --json
python3 scripts/run.py model-action --action tap-attendance-entry --json
python3 scripts/run.py model-action --action tap-back-icon --json
python3 scripts/run.py model-action --action back --json
python3 scripts/run.py model-action --action tap --x 100 --y 200 --json
```

动作完成后必须重新执行原命令或 `status`，不能假设动作成功。
