# 第三方署名 / Third-Party Attribution

## 原始 Blender 模型

- 文件：`企鹅高松灯.blend`
- 内容：`mesh0`（企鹅身体）+ `Tomori_mesh`（高松灯头部）
- 来源：由本项目作者提供使用；原始文件未标注作者与来源信息。
  若你是该模型的作者并希望补充署名或要求移除，请通过 Issue 联系。

本项目使用了该 .blend 文件作为唯一输入，做了以下修改：

1. 坐标轴转换：Blender Z-up 映射为 SA ped 轴向（X=上 / Y=前 / Z=左右），
   整体缩放到与基准 ped `WM1.dff` 等高（1.93）。
2. 几何处理：清除源文件 68 个 shape key（避免几何塌陷）；头部分离后按
   `" Spine1"` 摆正居中。
3. 蒙皮：身体使用 32 根标准 SA ped 骨骼自动权重；手臂/翅膀组重映射到
   `" L UpperArm"` / `" L ForeArm"` / `" L Hand"` 及右侧同名骨骼；
   保留前 4 权重并归一化。
4. 翅膀姿态：绕肩骨骼旋转（`WING_SCALE = 0.65`），再按躯干半径轮廓顶出体表
   （`PR_MARGIN = 0.06`）并整体外扩（`WING_OUT = 0.10`）；两种位移合并为一个
   位移场，在翅膀网格上做 8 次拉普拉斯平滑，消除肩部折痕。
5. 贴图：源材质烘焙为 1024×1024 贴图 `tomori_baked.png`，打包进 `tomori.txd`；
   提亮处理（gamma 0.58、×1.15，Base Color 置 1.0）修正游戏内偏暗。
6. 顶点色：移除全部顶点色层，避免 SA 将其作为 prelight 导致模型发暗。

## 角色版权

「高松灯 / ともり」角色形象版权归其原作者 / 版权方所有。
本仓库仅提供面向 GTA:SA 的技术格式转换，不声称拥有角色版权，且不允许商业使用。

## 工具

- Blender 5.0 + [DragonFF](https://github.com/Parik27/DragonFF)（DFF/TXD 导入导出）
- 皮肤 ID → 模型名对照表参考 SA-MP 社区皮肤列表
