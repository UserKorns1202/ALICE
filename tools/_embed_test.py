from tools.embeddings import EmbeddingClient

if __name__ == '__main__':
    c = EmbeddingClient()
    texts = ['hello world', 'test']
    embs = c.embed_texts(texts)
    print('count', len(embs))
    print('dim', len(embs[0]) if embs else None)
    # print first 5 values of first embedding for inspection
    if embs:
        print('first5', embs[0][:5])
