# Neural complexity
A neural language model that operates over words (based on the Pytorch word language model example) and has a number of improvements for testing on new data.

### Quick Usage
To train a Wikitext-2 LSTM model on GPUs:

    time python main.py --model_file 'wiki_2_model.pt' --vocab_file 'wiki_2_vocab.bin' --tied --cuda --data './data/wikitext-2/' --trainfname 'train.txt' --validfname 'valid.txt'

To use that model to obtain incremental complexity estimates for the Wikitext-2 test partition:

    time python main.py --model_file 'wiki_2_model.pt' --vocab_file 'wiki_2_vocab.bin' --cuda --data './data/wikitext-2/' --testfname 'test.txt' --test --words --nopp > FILENAME.OUTPUT

To instead use the trained model interactively:

    time python main.py --model_file 'wiki_2_model.pt' --vocab_file 'wiki_2_vocab.bin' --cuda --data './data/wikitext-2/' --interact

## Features
* Outputs incremental word-by-word information-theoretic complexity estimates (i.e. surprisal, entropy, entropy reduction) if the runtime command `--words` is given.
* Can operate interactively
* Early convergence detection (when loss is the same for 3 consecutive training epochs)
* Any words in the test corpus which were not seen during training are converted to `<unk>`. The probability of `<unk>` can be explicitly trained on `<unk>` tokens in the training data and/or implicitly learned using new words seen during validation.
* Can operate directly on gzipped corpora
* Does not require training data to be present at test time
* Can handle blank lines and unicode characters in the input corpora
* Can handle plaintext vocabularies (interpretable by humans, 1/3 the size, and only a few ms slower to load)

### Model parameters
These parameters help specify the model  

    --model {RNN_TANH, RNN_RELU, LSTM, GRU}: Uses the specified type of model (default: LSTM)  
    --emsize [INT]: The number of dimensions in the word embedding input layer (default: 200)  
    --nhid [INT]: The number of hidden units in each layer (default: 2)  
    --nlayers [INT]: The number of layers (default: 2)  
    --lr [FLOAT]: The learning rate; gradient is multiplied by this during weight updates (default: 20)  
    --clip [FLOAT]: Clips gradients to dampen large updates (default: 0.25)  
    --epochs [INT]: Maximum number of training epochs (default: 40)  
                    Training will stop early if the loss remains the same for three consecutive epochs  
    --batch_size [INT]: Number of parallel sequences to process simultaneously (default: 20)  
    --bptt [INT]: How far back in time to propagate error (default: 35)  
    --dropout [FLOAT]: Proportion of the network to drop out during training (default: 0.2)  
    --tied: If present, ties word embedding weights to output weights (default: absent)  
    --seed [INT]: Random seed (default: 1111)  
    --cuda: If present, uses GPUs/CUDA (default: absent)  
    
### Data parameters
These parameters specify the data to use

    --model_file [PATH]: Path for saving/loading trained model (default: model.pt)  
    --data_dir [PATH]: Directory of the corpus data (default: data/wikitext-2)  
    --vocab_file [PATH]: Path to store the training vocab (default: vocab.bin)  
    --trainfname [FILE]: Name of training file within the data directory (default: train.txt)  
    --validfname [FILE]: Name of validation file within the data directory (default: valid.txt)  
    --testfname [FILE]: Name of test file within the data directory (default: test.txt)
    
### Runtime parameters
These parameters specify runtime options for using the model

    --single: If present with --cuda, use only a single GPU even if more are present (default: absent)  
    --test: If present, operate on test data; otherwise, train the model (default: absent)  
    --interact: If present, load the model for interactive use (default: absent)  
    --nopp: If present, suppress evaluation perplexity output (default: absent)  
    --words: If present, output word-by-word complexity instead of sentence-level loss (default: absent)  
    --csep [CHAR]: Use specified character as separator for complexity output (default: ' ')  
    
    --guess: If present, display model's best guess(es) at each time step (default: absent)
    --guessn [INT]: Number of guesses for model to make at each time step (default: 1)  
    --guessscores: If present, output unnormalized guess scores along with each guess (default: absent)  
    --guessratios: If present, output guess scores normalized by best guess (default: absent)  
    --guessprobs: If present, output guess probabilities along with each guess (default: absent)  
    --complexn [INT]: Compute complexity over best N guesses instead of over full vocab (default: 0 aka full vocab)  
