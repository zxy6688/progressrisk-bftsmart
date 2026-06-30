from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from pbft_progress_sim import AttackModel, NetworkContext, SimulationConfig
from pbft_progress_sim.metrics import expected_calibration_error
from pbft_progress_sim.simulation import (
    run_context_confounding_experiment,
    run_policy_experiment,
)

ROBUST_ATTACK_GRID = (
    AttackModel(primary_withhold_prob=0.55, backup_withhold_prob=0.45),
    AttackModel(primary_withhold_prob=0.70, backup_withhold_prob=0.60),
    AttackModel(primary_withhold_prob=0.90, backup_withhold_prob=0.75),
)


def aggregate(summary: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    return (
        summary.groupby(keys, as_index=False)
        .agg(
            any_failure_rate_mean=("any_failure_rate", "mean"),
            any_failure_rate_std=("any_failure_rate", "std"),
            top1_hit_rate_mean=("top1_hit_rate", "mean"),
            mean_brier_mean=("mean_brier", "mean"),
            mean_moved_nodes_mean=("mean_moved_nodes", "mean"),
            mean_controller_ms_mean=("mean_controller_ms", "mean"),
        )
    )


def attack_mismatch(config: SimulationConfig, seeds: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    heldout = AttackModel(primary_withhold_prob=0.65, backup_withhold_prob=0.60)
    point = AttackModel(primary_withhold_prob=0.90, backup_withhold_prob=0.75)
    rows=[]
    for model_name, grid in [("point_likelihood_ablation", None), ("hierarchical_regime_model", ROBUST_ATTACK_GRID)]:
        for policy in ["no_reconfig", "risk_triggered_random_partner", "risk_aware_exchange"]:
            for seed in range(seeds):
                result=run_policy_experiment(
                    config,
                    policy=policy,
                    seed=20000+seed,
                    attack=heldout,
                    likelihood_attack=point,
                    likelihood_attacks=grid,
                )
                row=result.policy_summary.copy()
                row["inference_model"]=model_name
                rows.append(row)
    x=pd.concat(rows,ignore_index=True)
    return x, aggregate(x,["inference_model","policy"]).sort_values(["inference_model","any_failure_rate_mean"])


def calibration(config: SimulationConfig, seeds: int) -> tuple[pd.DataFrame,float]:
    events=[]
    for seed in range(seeds):
        events.append(run_policy_experiment(config,"no_reconfig",80000+seed,likelihood_attacks=ROBUST_ATTACK_GRID).events)
    x=pd.concat(events,ignore_index=True)
    x["bin"]=pd.cut(x.posterior_risk,bins=np.linspace(0,1,7),include_lowest=True)
    t=x.groupby("bin",observed=False).agg(n=("posterior_risk","size"),mean_predicted_risk=("posterior_risk","mean"),observed_frequency=("true_over_threshold","mean")).reset_index()
    ece=expected_calibration_error(x.posterior_risk.to_numpy(),x.true_over_threshold.to_numpy(),bins=6)
    t["ece"]=ece
    return t,ece


def context_replication(config: SimulationConfig, trials: int) -> tuple[pd.DataFrame,pd.DataFrame]:
    rows=[]
    for i in range(trials):
        frame=run_context_confounding_experiment(
            committee_size=config.shard_size,
            f=config.f,
            prior_active_fraction=config.prior_active_fraction,
            attack=AttackModel(),
            batches=60,
            particles=config.particles,
            calibration_batches=config.calibration_batches,
            seed=30000+i,
            n_shards=config.n_shards,
            global_active_budget=int(round(config.n_nodes*config.prior_active_fraction)),
        )
        frame["trial"]=i
        rows.append(frame)
    x=pd.concat(rows,ignore_index=True)
    y=x.groupby("model_context",as_index=False).agg(
        posterior_risk_mean=("posterior_threshold_risk","mean"),
        posterior_risk_std=("posterior_threshold_risk","std"),
        false_alarm_rate_50=("posterior_threshold_risk",lambda z:float((z>=0.5).mean())),
    )
    return x,y


def sensitivity(config: SimulationConfig, seeds: int) -> tuple[pd.DataFrame,pd.DataFrame]:
    rows=[]
    for frac in [0.20,0.24,0.28,0.32]:
        c=SimulationConfig(
            n_nodes=config.n_nodes,n_shards=config.n_shards,
            malicious_fraction=frac,prior_active_fraction=frac,
            epochs=config.epochs,batches_per_epoch=config.batches_per_epoch,
            particles=config.particles,calibration_batches=config.calibration_batches,
            prediction_samples=config.prediction_samples,candidate_partners=config.candidate_partners,
            max_exchange_k=config.max_exchange_k,migration_penalty=config.migration_penalty,
            minimum_predicted_gain=config.minimum_predicted_gain,
            periodic_reshuffle_every=config.periodic_reshuffle_every,
        )
        for policy in ["no_reconfig","risk_aware_exchange"]:
            for seed in range(seeds):
                r=run_policy_experiment(c,policy,70000+round(frac*1000)+seed,likelihood_attacks=ROBUST_ATTACK_GRID)
                row=r.policy_summary.copy();row["malicious_fraction"]=frac;rows.append(row)
    x=pd.concat(rows,ignore_index=True)
    y=aggregate(x,["malicious_fraction","policy"]).sort_values(["malicious_fraction","policy"])
    return x,y


def budget_sweep(config: SimulationConfig,seeds:int) -> tuple[pd.DataFrame,pd.DataFrame]:
    rows=[]
    for kmax in [1,3,6,9]:
        c=SimulationConfig(
            n_nodes=config.n_nodes,n_shards=config.n_shards,
            malicious_fraction=config.malicious_fraction,prior_active_fraction=config.prior_active_fraction,
            epochs=config.epochs,batches_per_epoch=config.batches_per_epoch,
            particles=config.particles,calibration_batches=config.calibration_batches,
            prediction_samples=config.prediction_samples,candidate_partners=config.candidate_partners,
            max_exchange_k=kmax,migration_penalty=config.migration_penalty,
            minimum_predicted_gain=config.minimum_predicted_gain,
            periodic_reshuffle_every=config.periodic_reshuffle_every,
        )
        for seed in range(seeds):
            r=run_policy_experiment(c,"risk_aware_exchange",91000+kmax*100+seed,likelihood_attacks=ROBUST_ATTACK_GRID)
            row=r.policy_summary.copy();row["max_exchange_k"]=kmax;rows.append(row)
    x=pd.concat(rows,ignore_index=True)
    y=aggregate(x,["max_exchange_k"]).sort_values("max_exchange_k")
    return x,y


def prior_misspecification(config: SimulationConfig,seeds:int) -> tuple[pd.DataFrame,pd.DataFrame]:
    rows=[]
    for assumed in [0.20,0.24,0.28]:
        c=SimulationConfig(
            n_nodes=config.n_nodes,n_shards=config.n_shards,
            malicious_fraction=config.malicious_fraction,prior_active_fraction=assumed,
            epochs=config.epochs,batches_per_epoch=config.batches_per_epoch,
            particles=config.particles,calibration_batches=config.calibration_batches,
            prediction_samples=config.prediction_samples,candidate_partners=config.candidate_partners,
            max_exchange_k=config.max_exchange_k,migration_penalty=config.migration_penalty,
            minimum_predicted_gain=config.minimum_predicted_gain,
            periodic_reshuffle_every=config.periodic_reshuffle_every,
        )
        for seed in range(seeds):
            r=run_policy_experiment(c,"risk_aware_exchange",96000+round(assumed*1000)+seed,likelihood_attacks=ROBUST_ATTACK_GRID)
            row=r.policy_summary.copy();row["assumed_active_fraction"]=assumed;rows.append(row)
    x=pd.concat(rows,ignore_index=True)
    y=aggregate(x,["assumed_active_fraction"]).sort_values("assumed_active_fraction")
    return x,y


def save_plot(df: pd.DataFrame,x:str,y:str,hue:str,path:Path,title:str,ylabel:str) -> None:
    fig,ax=plt.subplots(figsize=(7.2,4.8))
    for label,sub in df.groupby(hue):
        ax.plot(sub[x],sub[y],marker="o",label=str(label))
    ax.set_xlabel(x.replace('_',' '));ax.set_ylabel(ylabel);ax.set_title(title);ax.legend();fig.tight_layout();fig.savefig(path,dpi=220);plt.close(fig)


def main()->None:
    p=argparse.ArgumentParser()
    p.add_argument('--seeds',type=int,default=12)
    p.add_argument('--context-trials',type=int,default=80)
    p.add_argument('--sensitivity-seeds',type=int,default=8)
    p.add_argument('--budget-seeds',type=int,default=8)
    p.add_argument('--prior-seeds',type=int,default=8)
    p.add_argument('--out',type=Path,default=Path('validation_v16'))
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    c=SimulationConfig()
    x,y=attack_mismatch(c,a.seeds);x.to_csv(a.out/'attack_mismatch_by_seed.csv',index=False);y.to_csv(a.out/'attack_mismatch_aggregate.csv',index=False)
    cal,ece=calibration(c,a.seeds);cal.to_csv(a.out/'calibration_curve.csv',index=False)
    fig,ax=plt.subplots(figsize=(5.6,5));valid=cal[cal.n>0];ax.plot([0,1],[0,1],'--',label='ideal');ax.plot(valid.mean_predicted_risk,valid.observed_frequency,marker='o',label=f'ECE={ece:.3f}');ax.set_xlabel('mean posterior risk');ax.set_ylabel('observed frequency');ax.set_title('Calibration');ax.legend();fig.tight_layout();fig.savefig(a.out/'fig_calibration.png',dpi=220);plt.close(fig)
    cx,cy=context_replication(c,a.context_trials);cx.to_csv(a.out/'context_replications.csv',index=False);cy.to_csv(a.out/'context_replication_aggregate.csv',index=False)
    sx,sy=sensitivity(c,a.sensitivity_seeds);sx.to_csv(a.out/'sensitivity_by_seed.csv',index=False);sy.to_csv(a.out/'sensitivity_aggregate.csv',index=False);save_plot(sy,'malicious_fraction','any_failure_rate_mean','policy',a.out/'fig_sensitivity.png','Adversarial-fraction sensitivity','failure-epoch fraction')
    bx,by=budget_sweep(c,a.budget_seeds);bx.to_csv(a.out/'budget_by_seed.csv',index=False);by.to_csv(a.out/'budget_aggregate.csv',index=False)
    fig,ax=plt.subplots(figsize=(6.6,4.8));ax.plot(by.max_exchange_k,by.any_failure_rate_mean,marker='o');ax.set_xlabel('maximum exchange size k');ax.set_ylabel('failure-epoch fraction');ax.set_title('Migration-budget sweep');fig.tight_layout();fig.savefig(a.out/'fig_budget.png',dpi=220);plt.close(fig)
    px,py=prior_misspecification(c,a.prior_seeds);px.to_csv(a.out/'prior_misspecification_by_seed.csv',index=False);py.to_csv(a.out/'prior_misspecification_aggregate.csv',index=False)
    fig,ax=plt.subplots(figsize=(6.6,4.8));ax.plot(py.assumed_active_fraction,py.any_failure_rate_mean,marker='o');ax.set_xlabel('assumed global active fraction');ax.set_ylabel('failure-epoch fraction');ax.set_title('Threat-budget misspecification');fig.tight_layout();fig.savefig(a.out/'fig_prior_misspecification.png',dpi=220);plt.close(fig)
    print(f'Wrote v1.6 validation to {a.out.resolve()}')

if __name__=='__main__':
    main()
