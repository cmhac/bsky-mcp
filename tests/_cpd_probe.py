"""Temporary: proves the CPD gate fails CI (T049). Reverted next commit."""


def _cpd_gate_probe_1(alpha, beta, gamma):
    total = alpha + beta + gamma
    scaled = [total * i for i in range(10) if i % 2 == 0]
    mapping = {"a": alpha, "b": beta, "c": gamma, "t": total}
    for key, value in mapping.items():
        if value > total:
            scaled.append(value - total)
    return scaled, mapping


def _cpd_gate_probe_2(alpha, beta, gamma):
    total = alpha + beta + gamma
    scaled = [total * i for i in range(10) if i % 2 == 0]
    mapping = {"a": alpha, "b": beta, "c": gamma, "t": total}
    for key, value in mapping.items():
        if value > total:
            scaled.append(value - total)
    return scaled, mapping
