import pathlib
import warnings
from typing import AsyncIterator, Type

import spacy
from spacy.util import minibatch, compounding

from dffml import (
    config,
    field,
    entrypoint,
    ModelNotTrained,
    Accuracy,
    SourcesContext,
    Record,
)
from dffml.model.model import Model
from dffml.model.model import ModelContext, ModelNotTrained


@config
class SpacyNERConfig:
    output_dir: pathlib.Path = field("Output directory")
    model: str = field(
        "Model name. Defaults to blank 'en' model.", default=None
    )
    n_iter: int = field("Number of training iterations", default=10)
    dropout: float = field(
        "Dropout rate to be used during training", default=0.5
    )


class SpacyNERModelContext(ModelContext):
    def __init__(self, parent):
        super().__init__(parent)
        if self.parent.config.model is not None:
            self.nlp = spacy.load(
                self.parent.config.model
            )  # load existing model
            self.logger.debug("Loaded model '%s'" % self.parent.config.model)
        else:
            self.nlp = spacy.blank("en")  # create blank Language class
            self.logger.debug("Created blank 'en' model")

        if "ner" not in self.nlp.pipe_names:
            self.ner = self.nlp.create_pipe("ner")
            self.nlp.add_pipe(self.ner, last=True)
        # otherwise, get it so we can add labels
        else:
            self.ner = self.nlp.get_pipe("ner")

    async def _preprocess_data(self, sources: Sources):
        all_examples = []
        all_sources = sources.with_features(["sentence", "entities",])
        async for record in all_sources:
            all_examples.append((record["sentence"], record.entities))
        return all_examples

    async def train(self, sources: Sources):
        train_examples = await self._preprocess_data(sources)
        for _, entities in train_examples:
            for ent in entities:
                self.ner.add_label(ent[2])

        # get names of other pipes to disable them during training
        pipe_exceptions = ["ner", "trf_wordpiecer", "trf_tok2vec"]
        other_pipes = [
            pipe for pipe in self.nlp.pipe_names if pipe not in pipe_exceptions
        ]
        # only train NER
        with self.nlp.disable_pipes(*other_pipes), warnings.catch_warnings():
            # show warnings for misaligned entity spans once
            warnings.filterwarnings(
                "once", category=UserWarning, module="spacy"
            )
            if self.parent.config.model is None:
                self.nlp.begin_training()
            for itn in range(self.parent.config.n_iter):
                random.shuffle(train_examples)
                losses = {}
                batches = minibatch(
                    train_examples, size=compounding(4.0, 32.0, 1.001)
                )
                for batch in batches:
                    texts, annotations = zip(*batch)
                    self.nlp.update(
                        texts,  # batch of texts
                        annotations,  # batch of annotations
                        drop=self.parent.config.dropout,
                        losses=losses,
                    )
                self.logger.debug("Losses", losses)

        if self.parent.config.output_dir is not None:
            if not self.parent.config.output_dir.exists():
                self.parent.config.output_dir.mkdir()
            self.nlp.to_disk(self.parent.config.output_dir)
            self.logger.debug("Saved model to", self.parent.config.output_dir)

    async def accuracy(self, sources: SourcesContext) -> Accuracy:
        pass

    async def predict(self, sources: SourcesContext) -> AsyncIterator[Record]:
        pass


@entrypoint("spacyner")
class SpacyNERModel(Model):
    CONFIG = SpacyNERConfig
    CONTEXT = SpacyNERModelContext
