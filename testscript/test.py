from milvus import Milvus, DataType, __version__
from sklearn import preprocessing
import numpy as np
import logging
import random


class Test:
    def __init__(self, nvec):
        self.cname = "benchmark"
        self.fname = "feature"
        self.dim = 128
        self.client = Milvus("localhost", 19530)
        self.prefix = '/sift1b/binary_128d_'
        self.suffix = '.npy'
        self.vecs_per_file = 100000
        self.maxfiles = 1000
        self.insert_bulk_size = 5000
        self.nvec = nvec
        self.insert_cost = 0
        assert self.nvec >= self.insert_bulk_size & self.nvec % self.insert_bulk_size == 0

    def run(self):
        try:
            # step 1 create collection
            logging.info(f'step 1 create collection')
            self._create_collection()
            logging.info(f'step 1 complete')

            # step 2 fill data
            logging.info(f'step 2 fill data')
            self._fill_data()
            logging.info(f'step 2 complete')

            # step 3 create index
            logging.info(f'step 3 create index')
            self._create_index()
            logging.info(f'step 3 complete')

            # step 4 load
            logging.info(f'step 4 load')
            self._load_collection()
            logging.info(f'step 4 complete')

            # step 5 search
            logging.info(f'step 5 search')
            self._search()
            logging.info(f'step 5 complete')
            return True
        except AssertionError as ae:
            logging.exception(ae)
        except Exception as e:
            logging.error(f'test failed: {e}')
        finally:
            if self.insert_cost > 0:
                logging.info(f'insert speed: {self.nvec / self.insert_cost} vector per second')
        return False

    def _create_collection(self):
        logging.debug(f'create_collection() start')

        if self.client.has_collection(self.cname):
            logging.debug(f'collection {self.cname} existed')

            self.client.drop_collection(self.cname)
            logging.info(f'drop collection {self.cname}')

        logging.debug(f'before create collection: {self.cname}')
        self.client.create_collection(self.cname, {
            "fields": [{
                "name": self.fname,
                "type": DataType.FLOAT_VECTOR,
                "metric_type": "L2",
                "params": {"dim": self.dim},
                "indexes": [{"metric_type": "L2"}]
            }]
        })
        logging.info(f'created collection: {self.cname}')

        assert self.client.has_collection(self.cname)
        logging.debug(f'create_collection() finished')

    def _fill_data(self):
        logging.debug(f'fill_data() start')

        count = 0
        for i in range(0, self.maxfiles):
            filename = self.prefix + str(i).zfill(5) + self.suffix
            logging.debug(f'filename: {filename}')

            array = np.load(filename)
            logging.debug(f'numpy array shape: {array.shape}')

            step = self.insert_bulk_size
            for p in range(0, self.vecs_per_file, step):
                entities = [
                    {"name": self.fname, "type": DataType.FLOAT_VECTOR, "values": array[p:p + step][:].tolist()}]
                logging.debug(f'before insert slice: {p}, {p + step}')

                self.client.insert(self.cname, entities)
                logging.info(f'after insert slice: {p}, {p + step}')

                count += step
                logging.debug(f'insert count: {count}')

                if count == self.nvec:
                    logging.debug(f'inner break')
                    break
            if count == self.nvec:
                logging.debug(f'outer break')
                break

        logging.debug(f'before flush: {self.cname}')
        self.client.flush([self.cname])
        logging.info(f'after flush')

        stats = self.client.get_collection_stats(self.cname)
        logging.debug(stats)

        assert stats["row_count"] == self.nvec
        logging.debug(f'fill_data() finished')

    def _create_index(self):
        logging.debug(f'create_index() start')

        index_params = {
            "metric_type": "L2",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 1024}
        }
        self.client.create_index(self.cname, self.fname, index_params)
        logging.debug(f'create index {self.cname} : {self.fname} : {index_params}')

        logging.debug(f'create_index() finished')

    def _load_collection(self):
        logging.debug(f'load_collection() start')

        logging.debug(f'before load collection: {self.cname}')
        self.client.load_collection(self.cname)
        logging.debug(f'load_collection() finished')

    def _search(self):
        logging.debug(f'search() start')

        result = self.client.search(self.cname,
                                    {"bool": {"must": [{"vector": {
                                        self.fname: {
                                            "metric_type": "L2",
                                            "query": _gen_vectors(10, self.dim),
                                            "topk": 10,
                                            "params": {"nprobe": 10}
                                        }
                                    }}]}}
                                    )
        logging.debug(f'{result}')
        logging.debug(f'search() finished')


def _gen_vectors(num, dim):
    vectors = [[random.random() for _ in range(dim)] for _ in range(num)]
    vectors = preprocessing.normalize(vectors, axis=1, norm='l2')
    return vectors.tolist()
