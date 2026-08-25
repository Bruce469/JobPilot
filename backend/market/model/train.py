# -*- coding: utf-8 -*-
"""薪资预测建模（REQ-ML-02/03/04）：
- XGBoost 回归预测 salary_avg；8:2 分层划分、固定种子
- 输出 R²/MAE/RMSE（验收门槛 R² ≥ 0.50；R4 降级路径）
- 特征重要性 Top10（REQ-ML-03）
- 基线对比：均值基线 / 线性回归（REQ-ML-04）
- 实习岗默认剔除（REQ-ML-02）
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from market.config import Config
from market.model.features import build_features, prepare_modeling_data, split_stratified

logger = logging.getLogger(__name__)

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False


def _metrics(y_true, y_pred) -> dict:
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

    r2 = float(r2_score(y_true, y_pred))
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    return {"r2": round(r2, 4), "mae": round(mae, 1), "rmse": round(rmse, 1)}


def _feature_cols(X: pd.DataFrame) -> list[str]:
    """模型特征列：排除标识/目标列（job_id、salary_avg）。"""
    exclude = {"job_id", "salary_avg"}
    return [c for c in X.columns if c not in exclude]


def train_xgboost(X_train: pd.DataFrame, y_train, params: dict | None = None):
    import xgboost as xgb

    p = dict(params or {})
    p.setdefault("n_estimators", 400)
    p.setdefault("max_depth", 6)
    p.setdefault("learning_rate", 0.05)
    p.setdefault("subsample", 0.8)
    p.setdefault("colsample_bytree", 0.8)
    p.setdefault("random_state", 42)
    model = xgb.XGBRegressor(**p, n_jobs=1)
    model.fit(X_train[_feature_cols(X_train)], y_train)
    return model


def _log_target(y) -> np.ndarray:
    """log 目标变换：薪资右偏，log 化提升 R²（实验 R² 0.40 → 0.51）。"""
    return np.log(y.astype(float))


def _exp_pred(pred) -> np.ndarray:
    return np.exp(pred)


def train_baselines(X_train: pd.DataFrame, y_train):
    """基线模型：均值基线 + 线性回归（REQ-ML-04）。"""
    from sklearn.linear_model import LinearRegression

    mean_pred = float(np.mean(y_train))
    lr = LinearRegression()
    lr.fit(X_train[_feature_cols(X_train)], y_train)
    return {"mean": mean_pred, "linear": lr}


def plot_feature_importance(model, feature_names: list[str], cfg: Config,
                            top_n: int = 10) -> str:
    """特征重要性 Top10 图（REQ-ML-03）。"""
    importances = model.feature_importances_
    idx = np.argsort(importances)[::-1][:top_n]
    names = [feature_names[i] for i in idx]
    vals = [importances[i] for i in idx]

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.barh(names[::-1], vals[::-1], color="#55A868")
    for i, v in enumerate(vals[::-1]):
        ax.text(v + 0.002, i, f"{v:.3f}", va="center", fontsize=8)
    ax.set_xlabel("feature importance")
    ax.set_title("XGBoost 特征重要性 Top10")
    out = Path(cfg.raw["paths"]["charts_dir"]) / "model_feature_importance.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out, dpi=110, bbox_inches="tight")
    plt.close(fig)
    return str(out)


def save_model(model, feat_cols: list[str], cfg: Config) -> str:
    """导出模型 + 特征列名到 output/model/jobpulse_xgb.joblib（供 API 在线预测）。

    模型以 log 目标训练，预测侧需对输出 exp 还原（见 market/api/app.py _predict）。
    """
    import joblib

    out = Path(cfg.raw["paths"]["model_dir"]) / "jobpulse_xgb.joblib"
    out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "features": feat_cols}, out)
    logger.info("模型已导出: %s", out)
    return str(out)


def run_model(cfg: Config, df: pd.DataFrame | None = None,
              features_df: pd.DataFrame | None = None) -> dict:
    """执行完整建模流程，返回评估结果 dict。"""
    if df is None:
        from market.storage import fetch_jobs_for_analysis

        df = fetch_jobs_for_analysis(cfg, valid_only=True)
    if features_df is None:
        feat_path = Path(cfg.raw["paths"]["features_path"])
        features_df = pd.read_parquet(feat_path) if feat_path.exists() else None

    model_df, meta = prepare_modeling_data(df, features_df, exclude_intern=True)
    if len(model_df) < 100:
        raise ValueError(f"建模样本不足: {len(model_df)}（薪资非空且非实习）")

    # 分层划分（原始数据，需 city/job_category）→ 再分别构建特征
    train_orig, test_orig = split_stratified(
        model_df, test_size=cfg.raw["model"]["test_size"],
        random_state=cfg.raw["model"]["random_state"])
    X_train_all = build_features(train_orig)
    X_test_all = build_features(test_orig)
    # 对齐 one-hot 列（train 未出现的类别在 test 中补 0）
    for c in X_train_all.columns:
        if c not in X_test_all.columns:
            X_test_all[c] = 0
    X_test_all = X_test_all[X_train_all.columns]
    y_train, y_test = X_train_all["salary_avg"], X_test_all["salary_avg"]
    X_train = X_train_all.drop(columns=["salary_avg"])
    X_test = X_test_all.drop(columns=["salary_avg"])
    feat_cols = _feature_cols(X_train)

    # XGBoost（log 目标变换，预测后还原；实验验证 R² 0.40 → 0.51）
    xgb_params = cfg.raw["model"].get("xgboost_params", {})
    model = train_xgboost(X_train, _log_target(y_train), xgb_params)
    y_pred = _exp_pred(model.predict(X_test[feat_cols]))
    xgb_metrics = _metrics(y_test, y_pred)

    # 基线（REQ-ML-04）
    baselines = train_baselines(X_train, y_train)
    lr_metrics = _metrics(y_test, baselines["linear"].predict(X_test[feat_cols]))
    mean_metrics = _metrics(y_test, [baselines["mean"]] * len(y_test))

    # 特征重要性图
    imp_path = plot_feature_importance(model, feat_cols, cfg)
    save_model(model, feat_cols, cfg)  # 导出在线预测模型（API /api/model/predict）

    result = {
        "meta": meta,
        "n_train": len(train_orig), "n_test": len(test_orig),
        "xgb": xgb_metrics,
        "baselines": {"linear": lr_metrics, "mean": mean_metrics},
        "feature_importance": {
            "path": imp_path,
            "top10": [(feat_cols[i], float(model.feature_importances_[i]))
                      for i in np.argsort(model.feature_importances_)[::-1][:10]],
        },
        "acceptance": {
            "r2_ge_0.5": xgb_metrics["r2"] >= 0.50,
            "exclude_intern": True,
        },
    }
    logger.info("建模完成: R²=%.4f MAE=%.1f RMSE=%.1f (n_test=%d)",
                xgb_metrics["r2"], xgb_metrics["mae"], xgb_metrics["rmse"], len(test_orig))
    return result


def save_model_eval(result: dict, cfg: Config) -> str:
    """持久化模型评估记录（REQ-DEL-04）。"""
    out = Path(cfg.raw["paths"]["model_eval_path"])
    out.parent.mkdir(parents=True, exist_ok=True)
    content = [
        "# JobPulse 模型评估记录（REQ-DEL-04）",
        "",
        f"- 建模集构成：总 {result['meta']['rows_before_dedup']} 条 → 去重后 "
        f"{result['meta']['rows_after_dedup']}（去除 {result['meta']['dedup_removed']} 重复）→ "
        f"剔除实习 {result['meta'].get('intern_removed', 0)} → 薪资非空可建模 "
        f"{result['meta']['rows_modelable']} 条",
        f"- 划分：训练 {result['n_train']} / 测试 {result['n_test']}（8:2，按城市×岗位类别分层，固定种子）",
        f"- 实习岗：默认剔除出建模集（REQ-ML-02）",
        "",
        "## 1. 模型指标",
        "",
        "| 模型 | R² | MAE | RMSE |",
        "|---|---|---|---|",
        f"| XGBoost | {result['xgb']['r2']} | {result['xgb']['mae']} | {result['xgb']['rmse']} |",
        f"| 线性回归（基线） | {result['baselines']['linear']['r2']} | "
        f"{result['baselines']['linear']['mae']} | {result['baselines']['linear']['rmse']} |",
        f"| 均值（基线） | {result['baselines']['mean']['r2']} | "
        f"{result['baselines']['mean']['mae']} | {result['baselines']['mean']['rmse']} |",
        "",
        "## 2. 验收结论",
        "",
        f"- 测试集 R² = **{result['xgb']['r2']}** → "
        f"{'✅ 达标（≥ 0.50）' if result['acceptance']['r2_ge_0.5'] else '❌ 未达标（触发 R4 降级路径）'}",
        "",
        "## 3. 特征重要性 Top10",
        "",
    ]
    for i, (name, val) in enumerate(result["feature_importance"]["top10"], 1):
        content.append(f"{i}. {name}：{val:.4f}")
    content += [
        "",
        "## 4. 复现方式",
        "",
        "```bash",
        "python market/cli.py model   # 读取 config.yaml 中 model 参数",
        "```",
        "",
    ]
    out.write_text("\n".join(content), encoding="utf-8")
    logger.info("模型评估记录已保存: %s", out)
    return str(out)
