# Contributing

欢迎提交 Issue 和 Pull Request。

## 开发流程

1. 从 `main` 创建功能分支；
2. 保持检测、统计、可视化模块职责清晰；
3. 新功能尽量补充测试；
4. 提交前运行：

```bash
python -m compileall src app.py scripts
pytest -q
```

5. 修改用户可见行为时更新 README/CHANGELOG；
6. 涉及新模型或新数据集时，在 `THIRD_PARTY_NOTICES.md` 中补充来源与许可证。

## 提交信息建议

```text
feat: 新增批量 PCB 图片识别
fix: 修复切片重叠区域重复计数
model: 更新 PCB 元器件权重
 docs: 补充数据标注说明
```

## Release

可用版本发布遵循 `RELEASE_POLICY.md`。
