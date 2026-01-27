#!/usr/bin/env python3
"""
End-to-End ML Training Pipeline

Combines data export from database and model training into a single script.
This is the main entry point for training prediction models.

Usage:
    # Train all sports with default settings
    python scripts/run_training_pipeline.py

    # Train specific sports with hyperparameter tuning
    python scripts/run_training_pipeline.py --sports nba nfl --tune

    # Skip export if data files already exist
    python scripts/run_training_pipeline.py --skip-export --sports nba

    # Full pipeline with ensemble models
    python scripts/run_training_pipeline.py --model-type ensemble --tune
"""

import asyncio
import argparse
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import json

from loguru import logger

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))


async def run_export(
    sports: List[str],
    output_dir: str = "data/historical"
) -> Dict[str, Optional[str]]:
    """
    Export training data from database.

    Returns dict mapping sport to export path.
    """
    from scripts.export_training_data import TrainingDataExporter

    logger.info("=" * 60)
    logger.info("PHASE 1: Exporting Training Data")
    logger.info("=" * 60)

    exporter = TrainingDataExporter(output_dir=output_dir)
    results = await exporter.export_all(sports=sports, format="csv")

    # Log results
    for sport, path in results.items():
        if path:
            logger.info(f"  ✓ {sport.upper()}: {path}")
        else:
            logger.warning(f"  ✗ {sport.upper()}: No data exported")

    return results


def run_training(
    sports: List[str],
    model_type: str = "xgb",
    tune_hyperparams: bool = False,
    base_path: str = ".",
    save_path: str = "ml/saved_models"
) -> Dict[str, Any]:
    """
    Train models for specified sports.

    Returns training results for each sport.
    """
    from ml.training.train_all_sports import SportModelTrainer

    logger.info("\n" + "=" * 60)
    logger.info("PHASE 2: Training Models")
    logger.info("=" * 60)
    logger.info(f"  Sports: {sports}")
    logger.info(f"  Model type: {model_type}")
    logger.info(f"  Hyperparameter tuning: {tune_hyperparams}")

    trainer = SportModelTrainer(
        base_path=base_path,
        model_save_path=save_path
    )

    results = trainer.train_all(
        sports=sports,
        model_type=model_type,
        tune_hyperparams=tune_hyperparams
    )

    return results


def validate_models(
    sports: List[str],
    save_path: str = "ml/saved_models"
) -> Dict[str, bool]:
    """
    Validate that trained models can be loaded and make predictions.
    """
    import joblib
    import numpy as np

    logger.info("\n" + "=" * 60)
    logger.info("PHASE 3: Validating Models")
    logger.info("=" * 60)

    save_dir = Path(save_path)
    results = {}

    for sport in sports:
        sport_dir = save_dir / sport
        if not sport_dir.exists():
            logger.warning(f"  ✗ {sport.upper()}: No model directory found")
            results[sport] = False
            continue

        # Find most recent model file
        model_files = list(sport_dir.glob("*.joblib"))
        if not model_files:
            logger.warning(f"  ✗ {sport.upper()}: No model files found")
            results[sport] = False
            continue

        latest_model = max(model_files, key=lambda p: p.stat().st_mtime)

        try:
            model = joblib.load(latest_model)

            # Try a dummy prediction
            dummy_features = np.random.randn(1, 10)
            pred = model.predict(dummy_features)

            if pred is not None and len(pred) > 0:
                logger.info(f"  ✓ {sport.upper()}: Model validated ({latest_model.name})")
                results[sport] = True
            else:
                logger.warning(f"  ✗ {sport.upper()}: Model returned no predictions")
                results[sport] = False

        except Exception as e:
            logger.warning(f"  ✗ {sport.upper()}: Validation failed - {e}")
            results[sport] = False

    return results


def generate_report(
    export_results: Dict[str, Optional[str]],
    training_results: Dict[str, Any],
    validation_results: Dict[str, bool],
    output_path: str = "ml/saved_models/training_report.json"
) -> str:
    """
    Generate a comprehensive training report.
    """
    logger.info("\n" + "=" * 60)
    logger.info("Generating Training Report")
    logger.info("=" * 60)

    report = {
        'timestamp': datetime.now().isoformat(),
        'summary': {
            'sports_attempted': list(training_results.keys()),
            'sports_successful': [],
            'sports_failed': []
        },
        'export': {},
        'training': {},
        'validation': {}
    }

    for sport in training_results.keys():
        # Export status
        report['export'][sport] = {
            'path': export_results.get(sport),
            'success': export_results.get(sport) is not None
        }

        # Training status
        result = training_results[sport]
        if 'error' in result:
            report['training'][sport] = {
                'success': False,
                'error': result['error']
            }
            report['summary']['sports_failed'].append(sport)
        else:
            cv_agg = result.get('cv_results', {}).get('aggregate', {})
            report['training'][sport] = {
                'success': True,
                'model_path': result.get('model_path'),
                'cv_auc': cv_agg.get('auc'),
                'cv_log_loss': cv_agg.get('log_loss'),
                'cv_brier_score': cv_agg.get('brier_score'),
                'final_metrics': result.get('final_metrics', {})
            }

            if validation_results.get(sport, False):
                report['summary']['sports_successful'].append(sport)
            else:
                report['summary']['sports_failed'].append(sport)

        # Validation status
        report['validation'][sport] = {
            'success': validation_results.get(sport, False)
        }

    # Save report
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2, default=str)

    logger.info(f"Report saved to {output_file}")

    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("TRAINING PIPELINE COMPLETE")
    logger.info("=" * 60)

    n_success = len(report['summary']['sports_successful'])
    n_failed = len(report['summary']['sports_failed'])

    logger.info(f"  Successful: {n_success} sport(s)")
    logger.info(f"  Failed: {n_failed} sport(s)")

    for sport in report['summary']['sports_successful']:
        auc = report['training'][sport].get('cv_auc', 'N/A')
        if isinstance(auc, float):
            logger.info(f"    ✓ {sport.upper()}: AUC = {auc:.4f}")
        else:
            logger.info(f"    ✓ {sport.upper()}")

    for sport in report['summary']['sports_failed']:
        error = report['training'].get(sport, {}).get('error', 'Unknown error')
        logger.info(f"    ✗ {sport.upper()}: {error}")

    return str(output_file)


async def main():
    """Main entry point for the training pipeline."""
    parser = argparse.ArgumentParser(
        description="End-to-end ML training pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Train all sports
  python scripts/run_training_pipeline.py

  # Train NBA and NFL with hyperparameter tuning
  python scripts/run_training_pipeline.py --sports nba nfl --tune

  # Skip export (use existing CSV files)
  python scripts/run_training_pipeline.py --skip-export --sports nba

  # Use ensemble models
  python scripts/run_training_pipeline.py --model-type ensemble
        """
    )

    parser.add_argument(
        '--sports',
        nargs='+',
        default=['all'],
        help='Sports to train (nba, nfl, mlb, soccer, or all)'
    )
    parser.add_argument(
        '--model-type',
        choices=['xgb', 'ensemble', 'stacked'],
        default='xgb',
        help='Model architecture'
    )
    parser.add_argument(
        '--tune',
        action='store_true',
        help='Enable hyperparameter tuning with Optuna'
    )
    parser.add_argument(
        '--skip-export',
        action='store_true',
        help='Skip data export (use existing CSV files)'
    )
    parser.add_argument(
        '--skip-validation',
        action='store_true',
        help='Skip model validation'
    )
    parser.add_argument(
        '--data-dir',
        type=str,
        default='data/historical',
        help='Directory for training data'
    )
    parser.add_argument(
        '--model-dir',
        type=str,
        default='ml/saved_models',
        help='Directory to save models'
    )

    args = parser.parse_args()

    # Setup logging
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        level="INFO"
    )
    logger.add(
        f"training_pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
        rotation="100 MB",
        level="DEBUG"
    )

    # Normalize sports list
    if args.sports == ['all']:
        sports = ['nba', 'nfl', 'mlb', 'soccer']
    else:
        sports = [s.lower() for s in args.sports]

    logger.info("\n" + "=" * 60)
    logger.info("SPORTS PREDICTION MODEL TRAINING PIPELINE")
    logger.info("=" * 60)
    logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Sports: {sports}")
    logger.info(f"Model type: {args.model_type}")
    logger.info(f"Hyperparameter tuning: {args.tune}")

    # Phase 1: Export data (unless skipped)
    export_results = {}
    if not args.skip_export:
        export_results = await run_export(sports, args.data_dir)
    else:
        logger.info("Skipping data export (using existing files)")
        for sport in sports:
            path = Path(args.data_dir) / f"{sport}_historical_games.csv"
            export_results[sport] = str(path) if path.exists() else None

    # Check if we have data for any sport
    sports_with_data = [s for s, p in export_results.items() if p and Path(p).exists()]

    if not sports_with_data:
        logger.error("No training data available. Run backfill first:")
        logger.error("  python scripts/backfill_all_sports.py --sport all")
        return

    # Phase 2: Train models
    training_results = run_training(
        sports=sports_with_data,
        model_type=args.model_type,
        tune_hyperparams=args.tune,
        base_path=".",
        save_path=args.model_dir
    )

    # Phase 3: Validate models (unless skipped)
    validation_results = {}
    if not args.skip_validation:
        validation_results = validate_models(sports_with_data, args.model_dir)
    else:
        logger.info("Skipping model validation")
        for sport in sports_with_data:
            validation_results[sport] = True

    # Generate report
    report_path = generate_report(
        export_results,
        training_results,
        validation_results,
        f"{args.model_dir}/training_report.json"
    )

    logger.info(f"\nFull report: {report_path}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nPipeline cancelled.")
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        raise
