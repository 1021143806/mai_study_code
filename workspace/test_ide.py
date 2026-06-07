# -*- coding: utf-8 -*-
"""
简单的打印测试文件
"""

print("=" * 50)
print("欢迎使用麦麦的 IDE 测试工具")
print("=" * 50)

# 1. 基本打印
print("\n=== 1. 基本打印 ===")
print("Hello, World!")
print("你好，麦麦！")

# 2. 打印变量
print("\n=== 2. 打印变量 ===")
name = "麦麦"
age = 18
print(f"我叫{name}，今年{age}岁。")

# 3. 打印列表
print("\n=== 3. 打印列表 ===")
fruits = ["苹果", "香蕉", "橘子", "西瓜"]
print("水果列表:", fruits)
for i, fruit in enumerate(fruits, 1):
    print(f"  {i}. {fruit}")

# 4. 打印字典
print("\n=== 4. 打印字典 ===")
student = {
    "姓名": "小明",
    "年龄": 12,
    "爱好": ["编程", "画画", "读书"]
}
print("学生信息:", student)
for key, value in student.items():
    print(f"  {key}: {value}")

# 5. 打印表格
print("\n=== 5. 打印简单表格 ===")
print(f"{'姓名':<8}{'年龄':<5}{'成绩':<5}")
print("-" * 20)
print(f"{'小明':<8}{'12':<5}{'95':<5}")
print(f"{'小红':<8}{'11':<5}{'88':<5}")
print(f"{'小刚':<8}{'12':<5}{'92':<5}")

# 6. 打印图案
print("\n=== 6. 打印图案 ===")
for i in range(1, 6):
    print(" " * (5 - i) + "*" * (2 * i - 1))

# 7. 打印进度条
print("\n=== 7. 打印进度条 ===")
import time
for i in range(11):
    progress = "█" * i + "░" * (10 - i)
    print(f"\r进度: [{progress}] {i*10}%", end="")
    time.sleep(0.1)
print("\n")

# 8. 打印彩色文字（如果终端支持）
print("\n=== 8. 打印带样式的文字 ===")
print("\033[91m红色文字\033[0m")
print("\033[92m绿色文字\033[0m")
print("\033[93m黄色文字\033[0m")
print("\033[94m蓝色文字\033[0m")
print("\033[95m紫色文字\033[0m")

print("\n" + "=" * 50)
print("测试完成！")
print("=" * 50)
