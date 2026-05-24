import pulp

# === IEVADDATI (no 11. varianta) ===
m = 5
n = 19
Pmax = [25, 20, 15, 40, 20]
P = [7, 8, 5, 5, 6, 4, 4, 7, 6, 6, 8, 5, 4, 5, 5, 6, 8, 6, 5]
U = [90, 100, 40, 55, 35, 30, 50, 90, 85, 65, 50, 40, 20, 20, 15, 60, 40, 50, 35]
r = [2.0, 2.0, 1.3, 1.3, 1.0, 1.3, 1.3, 2.0, 1.7, 1.3, 1.3, 1.0, 1.0, 1.0, 1.0, 1.3, 1.0, 1.3, 1.0]
a = [0.3, 0.3, 0.2, 0.2, 0.15, 0.2, 0.2, 0.3, 0.3, 0.2, 0.2, 0.1, 0.1, 0.1, 0.1, 0.2, 0.15, 0.2, 0.1]
Y_size = [1, 1, 2, 2, 1, 1, 1, 2, 2, 1, 1, 1, 1, 1, 1, 2, 2, 2, 1]

# Korelācijas kopas Yj (0-bāzēts indekss)
Y = [
    [7], [2], [1, 3], [2, 4], [3], [6], [5], [0, 8],
    [7, 9], [8], [9], [12], [11], [14], [13],
    [16, 17], [15, 17], [15, 16], [16]
]

# AND priekšnosacījumi (jābūt VISIEM predikātiem)
AND_preds = {3: [2], 4: [3], 6: [5], 10: [9], 11: [10], 12: [10], 18: [16]}

# OR priekšnosacījumi (jābūt VISMĀZ VIENAM)
OR_preds = {9: [7, 8], 14: [13]}

stories = ["R.01","R.05","R.06","R.07","R.08","R.09","R.10","R.11",
           "R.14","R.15","R.16","R.17","R.18","R.19","R.20",
           "R.21","R.22","R.23","R.24"]

def solve_model(include_deps_and_corrs=False):
    prob = pulp.LpProblem("Sprint_Planning", pulp.LpMaximize)
    x = [[pulp.LpVariable(f"x_{i}_{j}", cat="Binary") for j in range(n)] for i in range(m)]
    y = None
    if include_deps_and_corrs:
        y = [[pulp.LpVariable(f"y_{i}_{j}", 0, Y_size[j], cat="Integer") for j in range(n)] for i in range(m)]

    # Mērķa funkcija
    obj = pulp.lpSum(U[j] * r[j] * pulp.lpSum(x[i][j] for i in range(m)) for j in range(n))
    if include_deps_and_corrs:
        for j in range(n):
            for i in range(m):
                obj += U[j] * a[j] * y[i][j] / Y_size[j]
    prob += obj

    # Kapacitātes ierobežojumi
    for i in range(m):
        prob += pulp.lpSum(P[j] * x[i][j] for j in range(n)) <= Pmax[i]

    # Katrs stāsts tieši vienā sprintā
    for j in range(n):
        prob += pulp.lpSum(x[i][j] for i in range(m)) == 1

    if include_deps_and_corrs:
        # AND nosacījumi
        for j, preds in AND_preds.items():
            d = len(preds)
            for i in range(m):
                sum_preds = pulp.lpSum(x[k][p] for k in range(i+1) for p in preds)
                prob += sum_preds >= d * x[i][j]
        # OR nosacījumi
        for j, preds in OR_preds.items():
            for i in range(m):
                sum_preds = pulp.lpSum(x[k][p] for k in range(i+1) for p in preds)
                prob += x[i][j] <= sum_preds
        # Korelācijas nosacījumi
        for j in range(n):
            for i in range(m):
                prob += y[i][j] <= pulp.lpSum(x[i][k] for k in Y[j])
                prob += y[i][j] <= Y_size[j] * x[i][j]

    # Risināšana
    prob.solve(pulp.PULP_CBC_CMD(msg=False))
    assignment = [[] for _ in range(m)]
    for i in range(m):
        for j in range(n):
            if pulp.value(x[i][j]) > 0.5:
                assignment[i].append(j)
    return {
        "status": pulp.LpStatus[prob.status],
        "objective": pulp.value(prob.objective),
        "assignment": assignment
    }

# === RISINĀJUMI ===
base = solve_model(include_deps_and_corrs=False)
full = solve_model(include_deps_and_corrs=True)

print("=== BĀZES MODELIS (bez atkarībām un korelācijām) ===")
print("Statuss:", base["status"])
print("Maksimālā vērtība Q =", base["objective"])
print("Sprintu plāns:")
for i, sts in enumerate(base["assignment"]):
    print(f"  Sprint {i+1} ({Pmax[i]} SP): {[stories[j] for j in sts]}")

print("\n=== PILNAIS MODELIS (ar visiem nosacījumiem) ===")
print("Statuss:", full["status"])
print("Maksimālā vērtība Q =", full["objective"])
print("Sprintu plāns:")
for i, sts in enumerate(full["assignment"]):
    print(f"  Sprint {i+1} ({Pmax[i]} SP): {[stories[j] for j in sts]}")