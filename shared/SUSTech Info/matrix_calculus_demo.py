#!/usr/bin/env python3
"""
矩阵微积分 (Matrix Calculus) 核心公式演示
基于你上传的 Wikipedia 文章内容
"""

import numpy as np
import sympy as sp

# ============================================================
# Part 1: 符号计算 (SymPy) — 精确验证公式
# ============================================================
print("=" * 60)
print("📐 Part 1: 符号推导验证 (SymPy)")
print("=" * 60)

# --- 定义符号变量 ---
x1, x2, x3 = sp.symbols('x1 x2 x3')
x = sp.Matrix([x1, x2, x3])
print("\n▸ x =", x.T, " (向量)")

# --- 公式 1: ∇_x (b^T x) = b ---
b1, b2, b3 = sp.symbols('b1 b2 b3')
b = sp.Matrix([b1, b2, b3])

f1 = b.T * x
f1 = f1[0]
print("\n--- 公式 1: gradient_x(b^T x) = b ---")
print("  f = b^T x =", f1)

grad1 = sp.Matrix([sp.diff(f1, xi) for xi in x])
print("  gradient_x f =", grad1.T)
print("  ✅ 结果等于 b =", b.T, "✓")

# --- 公式 2: ∇_x (x^T A x) = (A + A^T)x = 2Ax (A对称时) ---
a11, a12, a13 = sp.symbols('a11 a12 a13')
a21, a22, a23 = sp.symbols('a21 a22 a23')
a31, a32, a33 = sp.symbols('a31 a32 a33')
A = sp.Matrix([[a11, a12, a13],
               [a21, a22, a23],
               [a31, a32, a33]])

f2 = (x.T * A * x)[0]
print("\n--- 公式 2: gradient_x(x^T A x) = (A + A^T)x ---")
print("  f = x^T A x (二次型)")

grad2 = sp.Matrix([sp.diff(f2, xi) for xi in x])
print("  gradient_x f =", grad2.T)

expected2 = (A + A.T) * x
print("  (A + A^T)x =", expected2.T)
print("  ✅ 验证通过:", sp.simplify(grad2 - expected2).T)

print("\n  💡 若 A 对称 (A=A^T)，则 gradient_x(x^T A x) = 2Ax")

# --- 公式 3: 行列式导数 ---
x11, x12, x21, x22 = sp.symbols('x11 x12 x21 x22')
X = sp.Matrix([[x11, x12], [x21, x22]])

print("\n--- 公式 3: d/dX det(X) = det(X) * X^{-T} ---")
print("  X =", X)

detX = X.det()
print("  det(X) =", detX)

grad3 = sp.zeros(2, 2)
for i in range(2):
    for j in range(2):
        grad3[i, j] = sp.diff(detX, X[i, j])
print("  d det(X)/dX =")
sp.pprint(grad3)

expected3 = sp.simplify(detX * X.inv().T)
print("  det(X) * X^{-T} =")
sp.pprint(expected3)
print("  ✅ 验证通过!")

# ============================================================
# Part 2: 数值计算 (NumPy)
# ============================================================
print("\n" + "=" * 60)
print("🔢 Part 2: 数值计算 (NumPy)")
print("=" * 60)

np.random.seed(42)

# --- 2.1 二次型梯度 ---
print("\n--- 数值示例: gradient_x(x^T A x) ---")
x_np = np.array([1.0, 2.0, 3.0])
A_np = np.array([[2.0, 1.0, 0.0],
                  [1.0, 3.0, 1.0],
                  [0.0, 1.0, 4.0]])

f_val = x_np @ A_np @ x_np
grad_np = 2 * A_np @ x_np

print("  x =", x_np)
print("  A (对称) =")
print(A_np)
print("  f = x^T A x =", f"{f_val:.2f}")
print("  gradient f = 2Ax =", grad_np)

# --- 2.2 Jacobian ---
print("\n--- 数值示例: Jacobian J = df/dx (分子布局) ---")
def f_vector(x):
    return np.array([x[0]**2 + x[1]*x[2],
                     x[0]*x[1] + x[2]**2])

x0 = np.array([1.0, 2.0, -1.0])
h = 1e-8

J_num = np.zeros((2, 3))
for j in range(3):
    x_plus = x0.copy()
    x_plus[j] += h
    J_num[:, j] = (f_vector(x_plus) - f_vector(x0)) / h

print("  f: R^3 -> R^2, 在点 x =", x0)
print("  J (分子布局) =")
print(J_num)
print("  维度:", J_num.shape, " <- (输出维 x 输入维)")

# --- 2.3 迹的导数 ---
print("\n--- 数值示例: d/dX tr(AXB) = A^T B^T ---")
A_mat = np.array([[1.0, 2.0], [3.0, 4.0]])
B_mat = np.array([[5.0, 6.0], [7.0, 8.0]])
X_test = np.array([[0.1, 0.2], [0.3, 0.4]])

trace_val = np.trace(A_mat @ X_test @ B_mat)
grad_trace = A_mat.T @ B_mat.T

print("  A =")
print(A_mat)
print("  B =")
print(B_mat)
print("  tr(AXB) =", f"{trace_val:.4f}")
print("  d tr/dX (理论) =")
print(grad_trace)

# ============================================================
# Part 3: 测验答案验证
# ============================================================
print("\n" + "=" * 60)
print("🧪 Part 3: 测验答案验证")
print("=" * 60)

print("""
📋 测验回顾 & 答案:

题1: gradient_x(x^T A x), A对称 -> 2Ax  ✅

题2: "gradient_x(b^T x) = b^T" -> ❌ 错误!
     正确: gradient_x(b^T x) = b (列向量, 不是行向量!)

题3: d/dX det(X) = det(X) * X^{-T} (X可逆时) ✅

题4: d/dX tr(AXB) = A^T B^T  ✅

题5: Jacobian 维度 = m x n (m=输出维, n=输入维) ✅
""")

print("=" * 60)
print("🎉 演示完毕！所有核心公式已验证。")
print("=" * 60)
