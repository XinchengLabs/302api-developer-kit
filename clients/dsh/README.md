# DeepSeek Harness（DSH）

使用 [profile.patch.yaml](profile.patch.yaml) 的最小补丁，合并到现有 Profile 的 patch layer。

1. 将两处 `MODEL_ID_HERE` 替换为同一个、当前 Key 可用的模型 ID。
2. 在启动 DSH 的环境中设置 `ZH_API_KEY`，值为自己的 302API Key。
3. 保留现有 Profile 的其他 provider、插件、主题、权限和沙箱设置。
4. 重新加载配置并确认默认 provider 是 `api302`。

配置使用 `openai-completions`，地址沿用本站教程的兼容根入口 `https://api.302api.com`。这是 DSH 的配置方式；通用 OpenAI SDK 示例使用 `https://api.302api.com/v1`，不要机械地把不同客户端的 Base URL 互换。

## 图片输入

如果所选模型及本站对应路由支持图片输入，可在**该模型条目**增加：

```yaml
input: [text, image]
```

这只是客户端能力声明，不能让纯文本模型获得视觉能力。不要给所有模型统一添加。若仍然报“不支持”，需要区分客户端能力识别、实际请求协议及模型服务返回的错误。

本补丁不包含 `danger-full-access` 或取消审批配置，也不会替用户更改已有权限。
