"""Training loop and evaluation for the link prediction model."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import torch
import torch.nn.functional as F  # noqa: N812
from sklearn.metrics import average_precision_score
from sklearn.metrics import roc_auc_score
from torch_geometric.utils import negative_sampling

from nz_companies_office.config import SETTINGS

if TYPE_CHECKING:
    from collections.abc import Callable

    from nz_companies_office.models.link_predictor import LinkPredictor


@dataclass
class TrainingResult:
    """Outcome of a complete training run.

    Attributes:
        loss_history: Per-epoch training loss values.
        best_validation_auc: Highest AUC-ROC observed on the validation set.
        best_epoch: Epoch at which the best validation AUC was recorded.
        stopped_early: Whether training ended early due to patience being exceeded.

    """

    loss_history: list[float]
    best_validation_auc: float
    best_epoch: int
    final_epoch: int
    stopped_early: bool


@dataclass
class EvaluationResult:
    """Outcome of evaluating the model on an edge set.

    Attributes:
        auc: Area Under the ROC Curve.
        average_precision: Average Precision score.
        scores: Predicted probabilities (after sigmoid) for all edges.
        labels: Ground-truth binary labels for all edges.

    """

    auc: float
    average_precision: float
    scores: torch.Tensor
    labels: torch.Tensor


class LinkPredictorTrainer:
    """Trains a ``LinkPredictor`` with binary cross-entropy and early stopping.

    The trainer handles the full training loop: positive/negative edge sampling,
    loss computation, validation AUC tracking, checkpointing, and early stopping.
    A ``progress_callback`` can be provided to surface live metrics to the UI.

    Three separate graph objects prevent message-passing leakage across phases:
    - ``train_data``: only training shareholder edges (used during encoder training)
    - ``val_data``: training + validation shareholder edges (used for validation AUC)
    - ``test_data``: all shareholder edges (used for final evaluation)
    """

    def __init__(
        self,
        model: LinkPredictor,
        optimizer: torch.optim.Optimizer,
        train_data,  # noqa: ANN001
        val_data,  # noqa: ANN001
        test_data,  # noqa: ANN001
        training_edges: torch.LongTensor,
        validation_edges: torch.LongTensor,
        validation_negatives: torch.LongTensor,
        checkpoint_directory: Path | None = None,
    ) -> None:
        """Initialise the trainer with model, optimiser, and per-phase graph objects.

        Args:
            model: The ``LinkPredictor`` to train.
            optimizer: PyTorch optimiser (e.g. ``Adam``).
            train_data: ``HeteroData`` with only training shareholder edges
                (used for message passing during training).
            val_data: ``HeteroData`` with training + validation shareholder edges
                (used for message passing during validation).
            test_data: ``HeteroData`` with all shareholder edges
                (used for message passing during final evaluation).
            training_edges: 2xE tensor of positive training shareholder-company edges.
            validation_edges: 2xE tensor of positive validation edges.
            validation_negatives: 2xE tensor of negative validation edges.
            checkpoint_directory: Directory for saving model checkpoint files.

        """
        self.model = model
        self.optimizer = optimizer
        self.train_data = train_data
        self.val_data = val_data
        self.test_data = test_data
        self.training_edges = training_edges
        self.validation_edges = validation_edges
        self.validation_negatives = validation_negatives
        self.checkpoint_directory = checkpoint_directory or (SETTINGS.data_dir / "processed")
        Path(self.checkpoint_directory).mkdir(parents=True, exist_ok=True)

    def train(
        self,
        num_epochs: int = 50,
        patience: int = 20,
        progress_callback: Callable[[int, float, float, float], None] | None = None,
    ) -> TrainingResult:
        """Train the model with early stopping on validation AUC.

        Every 5 epochs the model is evaluated on the validation set. If the
        validation AUC does not improve for ``patience`` consecutive checks,
        training stops early. The best model weights are saved to
        ``model_checkpoint.pt``.

        Args:
            num_epochs: Maximum number of training epochs.
            patience: Number of validation checks without improvement before
                stopping.
            progress_callback: Optional callback invoked every 5 epochs with
                ``(epoch, loss, val_auc, best_auc)``. Useful for live progress
                display in notebooks.

        Returns:
            A ``TrainingResult`` containing the loss history and early stopping
            information.

        """
        loss_history: list[float] = []
        best_validation_auc: float = 0.0
        best_epoch: int = 0
        patience_counter: int = 0
        final_epoch: int = 0

        for epoch in range(1, num_epochs + 1):
            final_epoch = epoch
            epoch_loss = self._train_epoch()
            loss_history.append(epoch_loss)

            if epoch % 5 != 0:
                continue

            validation_auc = self._compute_validation_auc()

            if validation_auc > best_validation_auc:
                best_validation_auc = validation_auc
                best_epoch = epoch
                patience_counter = 0
                torch.save(self.model.state_dict(), self.checkpoint_directory / "model_checkpoint.pt")
            else:
                patience_counter += 1

            if progress_callback is not None:
                progress_callback(epoch, epoch_loss, validation_auc, best_validation_auc)

            if patience_counter >= patience:
                break

        return TrainingResult(
            loss_history=loss_history,
            best_validation_auc=best_validation_auc,
            best_epoch=best_epoch,
            final_epoch=final_epoch,
            stopped_early=patience_counter >= patience,
        )

    def _train_epoch(self) -> float:
        """Run one forward/backward pass on the training edges.

        Positive edges (real shareholder-company relationships) are scored high
        via ``logsigmoid``. Negative edges are sampled on the fly from random
        node pairs that are not in the training set, and scored low via
        ``logsigmoid(-score)``.

        Returns:
            The combined positive + negative loss for this epoch.

        """
        self.model.train()
        self.optimizer.zero_grad()

        # Encode using training-only graph to prevent test-edge leakage
        node_embeddings = self.model.encode(self.train_data)
        shareholder_embeddings = node_embeddings["shareholder"]
        company_embeddings = node_embeddings["company"]

        # Score positive edges and compute loss (push scores toward +inf)
        positive_scores = self.model.decoder(shareholder_embeddings, company_embeddings, self.training_edges)
        positive_loss = -F.logsigmoid(positive_scores).mean()

        # Sample negative edges and compute loss (push scores toward -inf)
        negative_edges = negative_sampling(
            self.training_edges,
            num_nodes=(self.train_data["shareholder"].num_nodes, self.train_data["company"].num_nodes),
            num_neg_samples=self.training_edges.shape[1],
        )
        negative_scores = self.model.decoder(shareholder_embeddings, company_embeddings, negative_edges)
        negative_loss = -F.logsigmoid(-negative_scores).mean()

        loss = positive_loss + negative_loss
        loss.backward()
        self.optimizer.step()

        return loss.item()

    def _compute_validation_auc(self) -> float:
        """Evaluate the model on the validation edge set.

        Computes dot-product scores for both positive and negative validation
        edges and returns the AUC-ROC (applied to raw logits — sigmoid is a
        monotonic transform so it does not affect AUC).

        Returns:
            AUC-ROC score on the validation set.

        """
        self.model.eval()
        with torch.no_grad():
            # Encode using train + validation graph for fair validation AUC
            node_embeddings = self.model.encode(self.val_data)
            shareholder_embeddings = node_embeddings["shareholder"]
            company_embeddings = node_embeddings["company"]

            positive_scores = self.model.decoder(
                shareholder_embeddings,
                company_embeddings,
                self.validation_edges,
            )
            negative_scores = self.model.decoder(
                shareholder_embeddings,
                company_embeddings,
                self.validation_negatives,
            )
            all_scores = torch.cat([positive_scores, negative_scores])
            all_labels = torch.cat(
                [torch.ones_like(positive_scores), torch.zeros_like(negative_scores)],
            )
            return roc_auc_score(all_labels.cpu().numpy(), all_scores.cpu().numpy())

    def evaluate(
        self,
        positive_edges: torch.LongTensor,
        negative_edges: torch.LongTensor,
        data=None,  # noqa: ANN001
    ) -> EvaluationResult:
        """Compute AUC-ROC and Average Precision for the given edge sets.

        Applies sigmoid to scores so they represent probabilities in [0, 1].

        Args:
            positive_edges: Ground-truth positive edges (2xE).
            negative_edges: Sampled negative edges (2xE).
            data: ``HeteroData`` to use for encoding. Defaults to ``self.test_data``
                (the full graph with all edges).

        Returns:
            An ``EvaluationResult`` with metrics and the score/label tensors
            (useful for plotting histograms and ROC curves).

        """
        if data is None:
            data = self.test_data
        self.model.eval()
        with torch.no_grad():
            node_embeddings = self.model.encode(data)
            shareholder_embeddings = node_embeddings["shareholder"]
            company_embeddings = node_embeddings["company"]

            positive_scores = self.model.decoder(
                shareholder_embeddings,
                company_embeddings,
                positive_edges,
            )
            negative_scores = self.model.decoder(
                shareholder_embeddings,
                company_embeddings,
                negative_edges,
            )
            all_scores = torch.sigmoid(torch.cat([positive_scores, negative_scores]))
            all_labels = torch.cat(
                [torch.ones_like(positive_scores), torch.zeros_like(negative_scores)],
            )

            scores_np = all_scores.cpu().numpy()
            labels_np = all_labels.cpu().numpy()

            return EvaluationResult(
                auc=roc_auc_score(labels_np, scores_np),
                average_precision=average_precision_score(labels_np, scores_np),
                scores=all_scores,
                labels=all_labels,
            )
