# Border collie / 基础边牧

Critter 自带的基础角色：黑白毛色、白色额纹与爪尖、鼠尾草绿项圈。透明画布为 256×256，GIF 每个 12 帧，持续循环。

| 文件 | 动作 | 每帧时间 |
| --- | --- | --- |
| `idle_sleep.gif` | 闭眼打盹、轻微呼吸 | 160 ms |
| `idle_walk.gif` | 原地踏步、尾巴摆动 | 100 ms |
| `interact_wash.gif` | 抬爪洗脸 | 100 ms |
| `interact_wag.gif` | 摇尾、眨眼 | 80 ms |
| `alert_run.gif` | 快速踏步与提醒标记；窗口移动由应用控制 | 60 ms |

## 来源与许可

这套素材是为本项目新绘制的程序化矢量图案。全部形状、配色和逐帧动作都定义在 [`tools/build_pet_assets.py`](../../../tools/build_pet_assets.py)，没有引用或下载第三方角色、图片、字体或动画。使用普通代码生成与本地渲染，没有调用图像生成服务。

SVG、GIF 与生成脚本均适用仓库根目录的 [MIT License](../../../LICENSE)，可按该许可修改和分发，并保留许可声明。`border_collie.svg` 是可直接打开的静态矢量预览；完整可编辑动作源为生成脚本。

## 重新生成

安装项目依赖后，在仓库根目录运行：

```bash
.venv/bin/python tools/build_pet_assets.py
```

脚本使用现有依赖 PyQt6 的 SVG 渲染器和 Pillow，不读取 `.env`、用户状态或网络。可使用 `--output /path/to/preview` 将素材写到其他目录。不同 Qt/Pillow 版本可能产生不同的编码字节；运行时直接读取已提交的 GIF，无需先生成。
