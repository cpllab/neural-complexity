import torch.nn as nn
from torch.autograd import Variable
import torch

class RNNModel(nn.Module):
    """Container module with an encoder, a recurrent module, and a decoder."""

    def __init__(self, rnn_type, ntoken, ninp, nhid, nlayers, dropout=0.5, tie_weights=False):
        super(RNNModel, self).__init__()
        self.drop = nn.Dropout(dropout)
        self.encoder = nn.Embedding(ntoken, ninp)
        if rnn_type in ['LSTM', 'GRU']:
            self.rnn = getattr(nn, rnn_type)(ninp, nhid, nlayers, dropout=dropout)
        else:
            try:
                nonlinearity = {'RNN_TANH': 'tanh', 'RNN_RELU': 'relu'}[rnn_type]
            except KeyError:
                raise ValueError( """An invalid option for `--model` was supplied,
                                 options are ['LSTM', 'GRU', 'RNN_TANH' or 'RNN_RELU']""")
            self.rnn = nn.RNN(ninp, nhid, nlayers, nonlinearity=nonlinearity, dropout=dropout)
        self.decoder = nn.Linear(nhid, ntoken)

        # Optionally tie weights as in:
        # "Using the Output Embedding to Improve Language Models" (Press & Wolf 2016)
        # https://arxiv.org/abs/1608.05859
        # and
        # "Tying Word Vectors and Word Classifiers: A Loss Framework for Language Modeling" (Inan et al. 2016)
        # https://arxiv.org/abs/1611.01462
        if tie_weights:
            if nhid != ninp:
                raise ValueError('When using the tied flag, nhid must be equal to emsize')
            self.decoder.weight = self.encoder.weight

        self.init_weights()

        self.rnn_type = rnn_type
        self.nhid = nhid
        self.nlayers = nlayers
        self.use_cache = False

    def init_weights(self):
        initrange = 0.1
        self.encoder.weight.data.uniform_(-initrange, initrange)
        self.decoder.bias.data.fill_(0)
        self.decoder.weight.data.uniform_(-initrange, initrange)

    def init_cache(self,cache_size=2000,cache_theta=0.3,cache_lambda=0.1,batch_size=10,cache_hidden_type='flat'):
        self.use_cache = True
        self.cache_size = cache_size
        self.cache_theta = cache_theta
        self.cache_lambda = cache_lambda
        self.cache_pointer = 0
        self.cache_hidden_type = cache_hidden_type ##{"top","bottom", "flat"}
        if self.cache_hidden_type == 'flat':
            self.hidden_cache = torch.cuda.FloatTensor(self.cache_size,batch_size,self.nhid*self.nlayers)
        else:
            self.hidden_cache = torch.cuda.FloatTensor(self.cache_size,batch_size,self.nhid)
        self.input_cache = torch.cuda.FloatTensor(self.cache_size,batch_size,self.encoder.num_embeddings)

    def reset_cache(self,batch_size=1):
        self.cache_pointer = 0
        if self.cache_hidden_type == 'flat':
            self.hidden_cache = torch.cuda.FloatTensor(self.cache_size,batch_size,self.nhid*self.nlayers)
        else:
            self.hidden_cache = torch.cuda.FloatTensor(self.cache_size,batch_size,self.nhid)
        self.input_cache = torch.cuda.FloatTensor(self.cache_size,batch_size,self.encoder.num_embeddings)

    def roll(tensor, shift, axis):
        if shift == 0:
            return tensor

        if axis < 0:
            axis += tensor.dim()

        dim_size = tensor.size(axis)
        after_start = dim_size - shift
        if shift < 0:
            after_start = -shift
            shift = dim_size - abs(shift)

        before = tensor.narrow(axis, 0, dim_size - shift)
        after = tensor.narrow(axis, after_start, shift)
        return torch.cat([after, before], axis)

    def forward(self, input, hidden):
        if not self.use_cache:
            emb = self.drop(self.encoder(input))
            output, hidden = self.rnn(emb, hidden)
            output = self.drop(output)
            decoded = self.decoder(output.view(output.size(0)*output.size(1), output.size(2)))
            return decoded.view(output.size(0), output.size(1), decoded.size(1)), hidden
        else:
            ## We're using the cache, so we need intermediate hidden states
            ## Therefore, we need to iterate over the time dimension
            output = torch.zeros(input.shape[0],input.shape[1],self.nhid)
            #print(self.input_cache[self.cache_pointer:self.cache_pointer+input.shape[0]].shape)
            #print(input.unsqueeze(2).shape)
            input_1hot = torch.cuda.FloatTensor(input.shape[0],input.shape[1],self.encoder.num_embeddings).zero_()
            input_1hot.scatter_(2,input.unsqueeze(2).data,1)
            self.input_cache[self.cache_pointer:self.cache_pointer+input.shape[0]] = input_1hot.clone()
            for seqix in range(input.shape[0]):
                ## step through the input
                emb_t = self.drop(self.encoder(input[seqix].unsqueeze(0)))
                output_t, hidden = self.rnn(emb_t, hidden)

                ## Cache shape is (batch_size,cache_cells)
                ##   if cache_hidden_type == 'flat': cache_cells = nhid * nlayers
                ##   else: cache_cells = nhid
                
                ## perform cache operations
                if self.cache_pointer == self.cache_size - 1:
                    ## Roll the cache
                    self.hidden_cache = roll(self.hidden_cache,0,-1)
                    self.input_cache = roll(self.input_cache,0,-1)
                ## Extend the cache to current time step
                if self.cache_hidden_type == 'top':
                    self.hidden_cache[self.cache_pointer] = hidden[0][-1,:,:].data.clone()
                    current_hidden = hidden[0][-1,:,:].data
                elif self.cache_hidden_type == 'bottom':
                    self.hidden_cache[self.cache_pointer] = hidden[0][0,:,:].data.clone()
                    current_hidden = hidden[0][0,:,:].data
                elif self.cache_hidden_type == 'flat':
                    #print(self.hidden_cache[self.cache_pointer,:,:].shape)
                    #print(hidden[0].view(hidden[0].shape[1],-1).data.shape)
                    self.hidden_cache[self.cache_pointer,:,:] = hidden[0].view(hidden[0].shape[1],-1).data.clone()
                    current_hidden = hidden[0].view(self.input_cache.shape[1],1,-1).data #hidden[0].shape[1],-1)

                if self.cache_pointer > 0:
                    ## Use the cached states
                    cache_query = torch.zeros(self.input_cache.shape[1],self.encoder.num_embeddings).cuda()
                    #hidden_cache_t = Variable(self.hidden_cache[0].view(self.input_cache.shape[1],-1,1))
                    #print(str(type(self.cache_theta)))
                    #print(type(torch.bmm(current_hidden, hidden_cache_t)),torch.bmm(current_hidden, hidden_cache_t).shape)
                    #print(str(type(torch.exp(self.cache_theta * torch.bmm(current_hidden, hidden_cache_t).data).cuda())),\
                    #      str(torch.exp(self.cache_theta * torch.bmm(current_hidden, hidden_cache_t).data).shape)
                    #      )
                    #print(str(cache_query.shape),\
                    #      str(torch.bmm(self.input_cache[1].view(self.input_cache.shape[1],self.encoder.num_embeddings,1),
                    #                    torch.exp(self.cache_theta * torch.bmm(current_hidden, hidden_cache_t).data).cuda()).shape),\
                    #      str(torch.bmm(self.input_cache[1].view(self.input_cache.shape[1],self.encoder.num_embeddings,1),torch.exp(self.cache_theta * torch.bmm(current_hidden, hidden_cache_t).data).cuda()).view(self.input_cache.shape[1],self.encoder.num_embeddings).shape))
                    hidden_cache_t = self.hidden_cache[0].view(self.input_cache.shape[1],-1,1)
                    print('cache_pointer',str(self.cache_pointer))
                    print('current_hidden',type(current_hidden))
                    print('hidden_cache_t',type(hidden_cache_t))
                    print('input_cache',type(self.input_cache[1].view(self.input_cache.shape[1],self.encoder.num_embeddings,1)))
                    print('exp1',type(torch.exp(self.cache_theta * torch.bmm(current_hidden, hidden_cache_t))),torch.exp(self.cache_theta * torch.bmm(current_hidden, hidden_cache_t)).shape)
                    print('exp2',type(torch.exp(self.cache_theta * torch.bmm(current_hidden, hidden_cache_t)).cuda()),torch.exp(self.cache_theta * torch.bmm(current_hidden, hidden_cache_t)).cuda().shape)
                    print('exp3',type(torch.exp(self.cache_theta * torch.bmm(current_hidden, hidden_cache_t)).cuda().view(-1,1,1)),torch.exp(self.cache_theta * torch.bmm(current_hidden, hidden_cache_t)).cuda().view(-1,1,1).shape)
                    for i in range(self.cache_pointer):
                        #hidden_cache_t = Variable(self.hidden_cache[i].view(self.input_cache.shape[1],-1,1))
                        hidden_cache_t = self.hidden_cache[i].view(self.input_cache.shape[1],-1,1)
                        cache_query += torch.bmm(self.input_cache[i + 1].view(self.input_cache.shape[1],self.encoder.num_embeddings,1),
                                                 torch.exp(self.cache_theta * torch.bmm(current_hidden, hidden_cache_t)).cuda())
                    print(self.decoder(output_t.view(output_t.size(0)*output_t.size(1), output_t.size(2))).shape)
                    print(cache_query.shape)
                    output_t = (1 - self.cache_lambda) * self.decoder(output_t.view(output_t.size(0)*output_t.size(1), output_t.size(2))) + self.cache_lambda * cache_query
                    raise
                    
                output[seqix,:,:] = output_t.data.clone()

                if self.cache_pointer != self.cache_size - 1:
                    self.cache_pointer += 1
    
            output = self.drop(output)
            decoded = self.decoder(output.view(output.size(0)*output.size(1), output.size(2)))
            return decoded.view(output.size(0), output.size(1), decoded.size(1)), hidden

    def init_hidden(self, bsz):
        weight = next(self.parameters()).data
        if self.rnn_type == 'LSTM':
            return (Variable(weight.new(self.nlayers, bsz, self.nhid).zero_()),
                    Variable(weight.new(self.nlayers, bsz, self.nhid).zero_()))
        else:
            return Variable(weight.new(self.nlayers, bsz, self.nhid).zero_())
