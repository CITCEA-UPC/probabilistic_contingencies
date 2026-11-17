"""Combinatòria física N−1/N−2 del catàleg."""
import unittest
from collections import Counter
from contingencies.catalogue import iter_contingencies


class CatalogueTests(unittest.TestCase):
    def test_cross_type_pairs_appear_once_and_never_disconnect_same_device_twice(self):
        rows=list(iter_contingencies(2,1,1))
        self.assertEqual(Counter(row[3] for row in rows),{1:4,2:6})
        keys=[]
        for lines,gens,trafos,level in rows:
            key=tuple((kind,i) for kind,ids in enumerate((lines,gens,trafos)) for i in ids)
            self.assertEqual(len(set(key)),level)
            keys.append(key)
        self.assertEqual(len(set(keys)),len(keys))
        self.assertEqual(keys[:4],[((0,0),),((0,1),),((1,0),),((2,0),)])

    def test_ieee118_has_239_single_and_28441_double_outages(self):
        counts=Counter(row[3] for row in iter_contingencies(175,53,11))
        self.assertEqual(counts,{1:239,2:28441})

    def test_empty_and_single_element_grids(self):
        self.assertEqual(list(iter_contingencies(0,0,0)),[])
        self.assertEqual(list(iter_contingencies(0,1,0)),[([],[0],[],1)])
        with self.assertRaises(ValueError): list(iter_contingencies(-1,0,0))


if __name__=='__main__': unittest.main()
