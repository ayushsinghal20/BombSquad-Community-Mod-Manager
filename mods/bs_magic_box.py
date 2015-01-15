#bs.gameTimer(1000, bs.WeakCall(setattr, bomb.node, 'velocity', [5, 10, 0]), repeat= True)
import random

import bs
import bsUtils

class MagicBox(bs.Bomb):
	def __init__(self,position=(0,1,0),velocity=(0,0,0),bombType='tnt',blastRadius=2.0,sourcePlayer=None,owner=None):
		"""
		Create a new Bomb.
		
		bombType can be 'ice','impact','landMine','normal','sticky', or 'tnt'.
		Note that for impact or landMine bombs you have to call arm()
		before they will go off.
		"""
		bs.Actor.__init__(self)

		factory = self.getFactory()

		self.bombType = bombType = 'tnt'

		self._exploded = False

		self.blastRadius = blastRadius
		
		# TNT
		self.blastRadius *= 1.45

		self._explodeCallbacks = []
		
		# the player this came from
		self.sourcePlayer = sourcePlayer

		# by default our hit type/subtype is our own, but we pick up types of whoever
		# sets us off so we know what caused a chain reaction
		self.hitType = 'explosion'
		self.hitSubType = self.bombType

		# if no owner was provided, use an unconnected node ref
		if owner is None: owner = bs.Node(None)

		# the node this came from
		self.owner = owner


		# TNT
		materials = (factory.bombMaterial, bs.getSharedObject('footingMaterial'), bs.getSharedObject('objectMaterial'))
		materials = materials + (factory.normalSoundMaterial,)

		
		self.node = bs.newNode('prop',
							   delegate=self,
							   attrs={'position':position,
									  'velocity':velocity,
									  'model':factory.tntModel,
									  'lightModel':factory.tntModel,
									  'body':'crate',
									  'shadowSize':0.5,
									  'colorTexture':factory.tntTex,
									  'reflection':'soft',
									  'reflectionScale':[0.23],
									  'materials':materials})

		
		#self.node.extraAcceleration = (0, 40, 0)
		self.heldBy = 0
		self._isDead = False
		

		bsUtils.animate(self.node,"modelScale",{0:0, 200:1.3, 260:1})

	def handleMessage(self, m):
		if isinstance(m, bs.PickedUpMessage):
			#self.heldBy += 1
			bs.getActivity()._updateBoxState()
			#self.updateFloatyness()
		elif isinstance(m, bs.DroppedMessage):
			#self.heldBy -= 1
			#self.updateFloatyness()
			bs.getActivity()._updateBoxState()
		elif isinstance(m, bs.DieMessage):
			if not self._isDead:
				bs.pushCall(bs.getActivity()._spawnBox)
			self._isDead = True
		super(self.__class__, self).handleMessage(m)

	def updateFloatyness(self):
		oldY = self.node.extraAcceleration[1]
		newY = {0: 0, 1: 39, 2: 19+20*2, 3: 19+20*3}.get(self.heldBy, 0)# needs more science
		time = 100 if (oldY > newY) else 1000
		keys = {0:   (0, oldY, 0),
				time: (0, newY, 0)}
		bs.animateArray(self.node, 'extraAcceleration', 3, keys)



def bsGetAPIVersion():
	return 3

def bsGetGames():
	return [MagicBoxGame]


class MagicBoxGame(bs.TeamGameActivity):

	BOX_NEW = 0
	BOX_UNCONTESTED = 1
	BOX_CONTESTED = 2
	BOX_HELD = 3

	@classmethod
	def getName(cls):
		return 'Magic Box'

	@classmethod
	def getDescription(cls,sessionType):
		return 'Grab the Box start flying.'

	@classmethod
	def getScoreInfo(cls):
		return {'scoreName':'Time Held'}

	@classmethod
	def supportsSessionType(cls,sessionType):
		return True if (issubclass(sessionType,bs.TeamsSession)
						or issubclass(sessionType,bs.FreeForAllSession)) else False

	@classmethod
	def getSupportedMaps(cls,sessionType):
		return bs.getMapsSupportingPlayType("keepAway")

	@classmethod
	def getSettings(cls,sessionType):
		return [("Hold Time",{'minValue':10,'default':30,'increment':10}),
				("Time Limit",{'choices':[('None',0),('1 Minute',60),
										('2 Minutes',120),('5 Minutes',300),
										('10 Minutes',600),('20 Minutes',1200)],'default':0}),
				("Respawn Times",{'choices':[('Shorter',0.25),('Short',0.5),('Normal',1.0),('Long',2.0),('Longer',4.0)],'default':1.0})]

	def __init__(self,settings):
		bs.TeamGameActivity.__init__(self,settings)
		self._scoreBoard = bs.ScoreBoard()
		self._swipSound = bs.getSound("swip")
		self._tickSound = bs.getSound('tick')
		self._countDownSounds = {10:bs.getSound('announceTen'),
								 9:bs.getSound('announceNine'),
								 8:bs.getSound('announceEight'),
								 7:bs.getSound('announceSeven'),
								 6:bs.getSound('announceSix'),
								 5:bs.getSound('announceFive'),
								 4:bs.getSound('announceFour'),
								 3:bs.getSound('announceThree'),
								 2:bs.getSound('announceTwo'),
								 1:bs.getSound('announceOne')}

	def getInstanceDescription(self):
		return ('Hold the magic box for ${ARG1} seconds.',self.settings['Hold Time'])

	def getInstanceScoreBoardDescription(self):
		return ('Hold the magic box for ${ARG1} seconds',self.settings['Hold Time'])

	def onTransitionIn(self):
		bs.TeamGameActivity.onTransitionIn(self, music='Keep Away')

	def onTeamJoin(self,team):
		team.gameData['timeRemaining'] = self.settings["Hold Time"]
		self._updateScoreBoard()

	def onBegin(self):
		bs.TeamGameActivity.onBegin(self)
		self.setupStandardTimeLimit(self.settings['Time Limit'])
		self.setupStandardPowerupDrops()
		self._boxSpawnPos = self.getMap().getFlagPosition(None)
		self._spawnBox()
		self._updateTimer = bs.Timer(1000,call=self._tick,repeat=True)
		self._updateBoxState()

	def _tick(self):
		self._updateBoxState()

		# award points to all living players holding the flag
		for player in self._holdingPlayers:
			if player.exists():
				self.scoreSet.playerScored(player,3,screenMessage=False,display=False)

		scoringTeam = self._scoringTeam
		
		if scoringTeam is not None:

			if scoringTeam.gameData['timeRemaining'] > 0: bs.playSound(self._tickSound)

			scoringTeam.gameData['timeRemaining'] = max(0,scoringTeam.gameData['timeRemaining']-1)
			self._updateScoreBoard()
			if scoringTeam.gameData['timeRemaining'] > 0:
				pass#self._box.setScoreText(str(scoringTeam.gameData['timeRemaining']))

			# announce numbers we have sounds for
			try: bs.playSound(self._countDownSounds[scoringTeam.gameData['timeRemaining']])
			except Exception: pass

			# winner
			if scoringTeam.gameData['timeRemaining'] <= 0:
				self.endGame()

	def endGame(self):
		results = bs.TeamGameResults()
		for team in self.teams: results.setTeamScore(team,self.settings['Hold Time'] - team.gameData['timeRemaining'])
		self.end(results=results,announceDelay=0)
		
	def _updateBoxState(self):
		for team in self.teams:
			team.gameData['holdingBox'] = False
		self._holdingPlayers = []
		for player in self.players:
			try:
				if player.actor.isAlive() and player.actor.node.holdNode.exists():
					holdingBox = (player.actor.node.holdNode == self._box.node)
				else: holdingBox = False
			except Exception:
				bs.printException("exception checking hold flag")
			if holdingBox:
				self._holdingPlayers.append(player)
				player.getTeam().gameData['holdingBox'] = True

		if self._box is not None and self._box.exists():
			self._box.heldBy = len(self._holdingPlayers)
			self._box.updateFloatyness()

		holdingTeams = set(t for t in self.teams if t.gameData['holdingBox'])
		#bs.screenMessage("holding: "+str(len(holdingTeams)))
		prevState = self._boxState
		if len(holdingTeams) > 1:
			self._boxState = self.BOX_CONTESTED
			self._scoringTeam = None
			#self._box.light.color = (0.6,0.6,0.1)
			#self._box.node.color = (1.0,1.0,0.4)
		elif len(holdingTeams) == 1:
			holdingTeam = list(holdingTeams)[0]
			self._boxState = self.BOX_HELD
			self._scoringTeam = holdingTeam
			#self._box.light.color = bs.getNormalizedColor(holdingTeam.color)
			#self._box.node.color = holdingTeam.color
		else:
			self._boxState = self.BOX_UNCONTESTED
			self._scoringTeam = None
			#self._box.light.color = (0.2,0.2,0.2)
			#self._box.node.color = (1,1,1)
		
		if self._boxState != prevState:
			bs.playSound(self._swipSound)

	def _spawnBox(self):
		bs.playSound(self._swipSound)
		self._flashBoxSpawn()
		self._box = MagicBox(position=self._boxSpawnPos)
		self._boxState = self.BOX_NEW
		self._box.light = bs.newNode('light',
									  owner=self._box.node,
									  attrs={'intensity':0.2,
											 'radius':0.3,
											 'color': (0.2,0.2,0.2)})
		self._box.node.connectAttr('position',self._box.light,'position')
		self._updateBoxState()

	def _flashBoxSpawn(self):
		light = bs.newNode('light',
						   attrs={'position':self._boxSpawnPos,'color':(1,1,1),
								  'radius':0.3,'heightAttenuated':False})
		bs.animate(light,'intensity',{0:0,250:0.5,500:0},loop=True)
		bs.gameTimer(1000,light.delete)

	def _updateScoreBoard(self):
		for team in self.teams:
			self._scoreBoard.setTeamValue(team,team.gameData['timeRemaining'],self.settings['Hold Time'],countdown=True)

	def handleMessage(self,m):
		if isinstance(m,bs.PlayerSpazDeathMessage):
			bs.TeamGameActivity.handleMessage(self,m) # augment default
			self.respawnPlayer(m.spaz.getPlayer())
		elif isinstance(m,bs.FlagDeathMessage):
			self._spawnBox()
		else: bs.TeamGameActivity.handleMessage(self,m)
