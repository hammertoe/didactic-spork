from struct import pack, unpack, unpack_from, calcsize
import unittest
from uuid import uuid4

class Wallet:

    HDR_FMT = "f"
    MSG_FMT = "16sf"

    def __init__(self, data=None):
        if data is not None:
            self.loads(data)
        else:
            self._total = 0.0
            self._bytes = ''
            self._num = 0

    def add(self, player_id, amount):
        data = pack(self.MSG_FMT, player_id, amount)
        self._bytes += data
        self._total += amount
        self._num += 1

    @property
    def total(self):
        return self._total

    def __len__(self):
        return self._num

    def dumps(self):
        return pack(self.HDR_FMT, self._total) + self._bytes

    def loads(self, data):
        hdr_len = calcsize(self.HDR_FMT)
        hdr,data = data[:hdr_len], data[hdr_len:]
        self._total = unpack(self.HDR_FMT, hdr)[0]
        self._bytes = data
        self._num = len(self._bytes) / calcsize(self.MSG_FMT)

    def __getitem__(self, index):
        if index >= self._num or index < 0:
            raise IndexError
        return unpack_from(self.MSG_FMT, self._bytes, index * calcsize(self.MSG_FMT))

    def todict(self):
        return dict(tuple(self))

    def transfer(self, amount, dest):
        if amount > self.total:
            raise ValueError, "Transfer amount too high"

        ratio = amount / self.total
        amounts = {}

        new_source = Wallet()
        new_dest = Wallet()

        # go through source wallet and work out how much to transfer
        # from each player as a ratio of the total amount
        # store that in amounts so we can add it later
        # construct a new source wallet with amounts deducted
        for player,balance in self:
            to_transfer = balance * ratio
            amounts[player] = to_transfer
            new_source.add(player, balance - to_transfer)

        # go through original destination wallet and add players from there
        # to new dest wallet incremented by the amount in amounts
        # remove from amounts when done
        for player,balance in dest:
            incr = amounts.get(player, 0.0)
            new_dest.add(player, balance+incr)
            if player in amounts:
                del amounts[player]

        # Go through what is left in amounts (new players to dest wallet)
        # and add them and their amount to the new wallet
        for player,balance in amounts.items():
            new_dest.add(player, balance)

        return new_source, new_dest
    
class WalletTests(unittest.TestCase):

    def testEmptyWallet(self):
        w = Wallet()
        self.assertEqual(len(w), 0)
        self.assertEqual(w.total, 0)

    def testAddItemToEmptyWallet(self):
        w = Wallet()
        player_id = uuid4()
        w.add(player_id.bytes, 23.3)
        self.assertEqual(len(w), 1)
        self.assertEqual(w.total, 23.3)

    def testAddSeveralItemsToWallet(self):
        w = Wallet()
        player_id = uuid4()
        w.add(player_id.bytes, 23.3)
        self.assertEqual(len(w), 1)
        self.assertEqual(w.total, 23.3)

        player_id = uuid4()
        w.add(player_id.bytes, 10.0)
        self.assertEqual(len(w), 2)
        self.assertEqual(w.total, 33.3)

    def testIndexIntoWallet(self):
        w = Wallet()
        player2_id = uuid4()
        player1_id = uuid4()

        w.add(player1_id.bytes, 23.3)
        w.add(player2_id.bytes, 10.0)

        self.assertEqual(w[0][0], player1_id.bytes)
        self.assertAlmostEqual(w[0][1], 23.3, 5)
        self.assertEqual(w[1][0], player2_id.bytes)
        self.assertAlmostEqual(w[1][1], 10.0, 5)

    def testIterateOverWallet(self):
        w = Wallet()
        player2_id = uuid4()
        player1_id = uuid4()

        w.add(player1_id.bytes, 23.3)
        w.add(player2_id.bytes, 10.0)

        w2 = tuple(w)

        self.assertEqual(w2[0][0], player1_id.bytes)
        self.assertAlmostEqual(w2[0][1], 23.3, 5)
        self.assertEqual(w2[1][0], player2_id.bytes)
        self.assertAlmostEqual(w2[1][1], 10.0, 5)

    def testIndexError(self):
        w = Wallet()
        player_id = uuid4()
        w.add(player_id.bytes, 10.0)
        with self.assertRaises(IndexError):
            a = w[1]

    def testToDict(self):
        w = Wallet()
        player1_id = uuid4().bytes
        player2_id = uuid4().bytes
        w.add(player1_id, 10.0)
        w.add(player2_id, 20.0)

        d = w.todict()
        self.assertEquals(d, {player1_id: 10,
                              player2_id: 20})


    def testTransferSingleToEmptyWallet(self):
        w1 = Wallet()
        player_id = uuid4()
        w1.add(player_id.bytes, 10.0)
        
        w2 = Wallet()
        w1, w2 = w1.transfer(4.0, w2)

        self.assertAlmostEqual(w1.total, 6.0)
        self.assertEqual(len(w1), 1)

        self.assertAlmostEqual(w2.total, 4.0)
        self.assertEqual(len(w2), 1)

    def testTransferSingleToWalletTheyAlreadyIn(self):
        w1 = Wallet()
        player_id = uuid4()
        w1.add(player_id.bytes, 10.0)
        
        w2 = Wallet()
        w2.add(player_id.bytes, 25.5)
        w1, w2 = w1.transfer(4.0, w2)

        self.assertAlmostEqual(w1.total, 6.0)
        self.assertEqual(len(w1), 1)

        self.assertAlmostEqual(w2.total, 29.5)
        self.assertEqual(len(w2), 1)

    def testTransferMultipleToEmptyWallet(self):
        w1 = Wallet()
        players = sorted([ uuid4().bytes for x in range(3) ])
        amounts = [10.0, 8.0, 6.0]

        for player,amount in zip(players,amounts):
            w1.add(player,amount)
        
        self.assertAlmostEqual(w1.total, 24.0)

        w2 = Wallet()
        w1, w2 = w1.transfer(6.0, w2)

        self.assertAlmostEqual(w1.total, 18.0)
        self.assertEqual(len(w1), 3)
        self.assertAlmostEqual(w1[0][1], 7.5)
        self.assertAlmostEqual(w1[1][1], 6.0)
        self.assertAlmostEqual(w1[2][1], 4.5)

        self.assertAlmostEqual(w2.total, 6.0)
        self.assertEqual(len(w2), 3)
        self.assertAlmostEqual(w2[0][1], 2.5 )
        self.assertAlmostEqual(w2[1][1], 2.0)
        self.assertAlmostEqual(w2[2][1], 1.5)

    def testTransferMultipleToEmptyWallet(self):
        w1 = Wallet()

        player1_id = uuid4().bytes
        player2_id = uuid4().bytes
        player3_id = uuid4().bytes

        w1.add(player1_id, 10.0)
        w1.add(player2_id, 8.0)
        w1.add(player3_id, 6.0)
        
        self.assertAlmostEqual(w1.total, 24.0)

        w2 = Wallet()
        w1, w2 = w1.transfer(6.0, w2)

        self.assertAlmostEqual(w1.total, 18.0)
        self.assertEqual(len(w1), 3)
        d1 = w1.todict()
        self.assertEqual(d1, {player1_id: 7.5,
                              player2_id: 6.0,
                              player3_id: 4.5})
        
        self.assertAlmostEqual(w2.total, 6.0)
        self.assertEqual(len(w2), 3)
        d2 = w2.todict()
        self.assertEqual(d2, {player1_id: 2.5,
                              player2_id: 2.0,
                              player3_id: 1.5})


    def testTransferMultipleToNonEmptyWallet1(self):
        w1 = Wallet()

        player1_id = uuid4().bytes
        player2_id = uuid4().bytes
        player3_id = uuid4().bytes

        w1.add(player1_id, 10.0)
        w1.add(player2_id, 8.0)
        w1.add(player3_id, 6.0)
        
        self.assertAlmostEqual(w1.total, 24.0)

        w2 = Wallet()
        w2.add(player1_id, 20.0)

        w1, w2 = w1.transfer(6.0, w2)

        self.assertAlmostEqual(w1.total, 18.0)
        self.assertEqual(len(w1), 3)
        d1 = w1.todict()
        self.assertEqual(d1, {player1_id: 7.5,
                              player2_id: 6.0,
                              player3_id: 4.5})
        
        self.assertAlmostEqual(w2.total, 26.0)
        self.assertEqual(len(w2), 3)
        d2 = w2.todict()
        self.assertEqual(d2, {player1_id: 22.5,
                              player2_id: 2.0,
                              player3_id: 1.5})

    def testTransferMultipleToNonEmptyWallet2(self):
        w1 = Wallet()

        player1_id = uuid4().bytes
        player2_id = uuid4().bytes
        player3_id = uuid4().bytes

        w1.add(player1_id, 10.0)
        
        self.assertAlmostEqual(w1.total, 10.0)

        w2 = Wallet()
        w2.add(player1_id, 20.0)
        w2.add(player2_id, 8.0)
        w2.add(player3_id, 6.0)

        self.assertAlmostEqual(w2.total, 34.0)

        w1, w2 = w1.transfer(6.0, w2)

        self.assertAlmostEqual(w1.total, 4.0)
        self.assertEqual(len(w1), 1)
        d1 = w1.todict()
        self.assertEqual(d1, {player1_id: 4.0,})
        
        self.assertAlmostEqual(w2.total, 40.0)
        self.assertEqual(len(w2), 3)
        d2 = w2.todict()
        self.assertEqual(d2, {player1_id: 26.0,
                              player2_id: 8.0,
                              player3_id: 6.0})

    def testDumpsLoads(self):
        w1 = Wallet()

        player1_id = uuid4().bytes
        player2_id = uuid4().bytes
        player3_id = uuid4().bytes

        w1.add(player1_id, 10.0)
        w1.add(player2_id, 20.0)
        w1.add(player3_id, 30.0)

        binary = w1.dumps()
        self.assertEqual(len(binary), 64)

        w2 = Wallet()
        w2.loads(binary)

        self.assertEqual(w1.total, w2.total)
        self.assertEqual(len(w1), len(w2))


if __name__ == '__main__':
    unittest.main()
