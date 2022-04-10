from datetime import datetime
import math
import sys
from Delaunator import Delaunator
import igraph
from Constants import Constants
from Tools import Tools

UNKNOWN = 1
UNWALKABLE = 2
WALKABLE = 3

class Pathfinder:
    G = None
    FIRST_MAP = 'main'
    TRANSPORT_COST = 50
    TOWN_COST = 450
    ENTER_COST = 1000

    grids = {}
    graph = igraph.Graph(directed = True)

    @staticmethod
    def doorDistance(a: dict, b: list) -> float:
        doorX = b[0]
        doorY = b[1]
        doorWidth = b[2]
        doorHeight = b[3]
        closest = sys.maxsize
        for x in range(int(doorX - doorWidth / 2), int(doorX + doorWidth / 2)):
            for y in range(int(doorY - doorHeight / 2), int(doorY + doorHeight / 2)):
                distance = Tools.distance(a, { 'x': x, 'y': y })
                if distance < closest:
                    closest = distance
        return closest

    @staticmethod
    def addLinkToGraph(fr, to, data=None):
        return Pathfinder.graph.add_edge(fr, to, data=data)
    
    @staticmethod
    def addNodeToGraph(_map: str, _x: int, _y: int):
        name = f"{_map}:{_x},{_y}"
        try:
            check = Pathfinder.graph.vs.select(name_eq=name)[0]
        except Exception:
            check = None
        if check != None:
            return check
        return Pathfinder.graph.add_vertex(name, map=_map, x=_x, y=_y)

    @staticmethod
    def canStand(location: dict) -> bool:
        if Pathfinder.G == None:
            raise Exception("Prepare pathfinding before querying canStand()!")
        
        y = math.trunc(location['y']) - Pathfinder.G['geometry'][location['map']]['min_y']
        x = math.trunc(location['x']) - Pathfinder.G['geometry'][location['map']]['min_x']
        width = Pathfinder.G['geometry'][location['map']]['max_x'] - Pathfinder.G['geometry'][location['map']]['min_x']

        try:
            grid = Pathfinder.getGrid(location['map'])
            if grid[y * width + x] == WALKABLE:
                return True
        except Exception:
            return False
        return False

    @staticmethod
    def canWalkPath(_from: dict, _to: dict) -> bool:
        if Pathfinder.G == None:
            raise Exception("Prepare pathfinding before querying canWalkPath()!")
        if _from['map'] != _to['map']:
            return False # We can't walk across maps
        
        grid = Pathfinder.getGrid(_from['map'])
        width = Pathfinder.G['geometry'][_from['map']]['max_x'] - Pathfinder.G['geometry'][_from['map']]['min_x']

        xStep = None
        yStep = None
        error = None
        errorPrev = None
        x = math.trunc(_from['x']) - Pathfinder.G['geometry'][_from['map']]['min_x']
        y = math.trunc(_from['y']) - Pathfinder.G['geometry'][_from['map']]['min_y']
        dx = math.trunc(_to['x']) - math.trunc(_from['x'])
        dy = math.trunc(_to['y']) - math.trunc(_from['y'])

        if grid[y * width + x] != WALKABLE:
            return False
        
        if dy < 0:
            yStep = -1
            dy = -dy
        else:
            yStep = 1
        if dx < 0:
            xStep = -1
            dx = -dx
        else:
            xStep = 1
        ddy = 2 * dy
        ddx = 2 * dx

        if ddx >= ddy:
            errorPrev = error = dx
            for i in range(0, dx):
                x += xStep
                error += ddy
                if error > ddx:
                    y += yStep
                    error -= ddx
                    if error + errorPrev < ddx:
                        if grid[(y - yStep) * width + x] != WALKABLE:
                            return False
                    elif error + errorPrev > ddx:
                        if grid[y * width + x - xStep] != WALKABLE:
                            return False
                    else:
                        if grid[(y - yStep) * width + x] != WALKABLE:
                            return False
                        if grid[y * width + x - xStep] != WALKABLE:
                            return False
                if grid[y * width + x] != WALKABLE:
                    return False
                errorPrev = error
        else:
            errorPrev = error = dy
            for i in range(0, dy):
                y += yStep
                error += ddx
                if error > ddy:
                    x += xStep
                    error -= ddy
                    if error + errorPrev < ddy:
                        if grid[y * width + x - xStep] != WALKABLE:
                            return False
                    elif error + errorPrev > ddy:
                        if grid[(y - yStep) * width + x] != WALKABLE:
                            return False
                    else:
                        if grid[y * width + x - xStep] != WALKABLE:
                            return False
                        if grid[(y - yStep) * width + x] != WALKABLE:
                            return False
                if grid[y * width + x] != WALKABLE:
                    return False
                errorPrev = error
        
        return True
    
    @staticmethod
    def computeLinkCost(fr, to, link, *, avoidTownWarps: bool = None, costs: dict[str, int] = {}) -> int:
        if Tools.hasKey(link, 'leave') or Tools.hasKey(link, 'transport'):
            if link['map'] == 'bank':
                return 1000
            if Tools.hasKey(costs, 'transport') and costs['transport'] != None:
                return costs['transport']
            else:
                return Pathfinder.TRANSPORT_COST
        elif Tools.hasKey(link, 'type') and link['type'] == 'enter':
            if Tools.hasKey(costs, 'enter') and costs['enter'] != None:
                return costs['enter']
            else:
                return Pathfinder.ENTER_COST
        elif Tools.hasKey(link, 'type') and link['type'] == 'town':
            if avoidTownWarps:
                return 999999
            else:
                if Tools.hasKey(costs, 'town') and costs['town'] != None:
                    return costs['town']
                else:
                    return Pathfinder.TOWN_COST
        
        if fr['map'] == to['map']:
            return Tools.distance(fr, to)

    @staticmethod
    def computePathCost(path: list, *, avoidTownWarps: bool = False, costs: dict[str, int] = {}) -> int:
        cost = 0
        current = path[0]
        for i in range(1, len(path)):
            next = path[i]
            cost += Pathfinder.computeLinkCost(current, next, next, avoidTownWarps=avoidTownWarps, costs=costs)
            current = next
        return cost
    
    @staticmethod
    def getGrid(map: str, base = Constants.BASE):
        if Tools.hasKey(Pathfinder.grids, map):
            return Pathfinder.grids[map]
        if Pathfinder.G == None:
            raise Exception("Prepare pathfinding before querying getGrid()!")

        gMap = Pathfinder.G['maps'][map]
        gGeo = Pathfinder.G['geometry'][map]
        minX = gGeo['min_x']
        maxX = gGeo['max_x']
        minY = gGeo['min_y']
        maxY = gGeo['max_y']
        width = maxX - minX
        height = maxY - minY

        grid = [UNKNOWN] * (height * width)

        for yLine in gGeo['y_lines']:
            lowerY = max([0, yLine[0] - minY - base['vn']])
            upperY = yLine[0] - minY + base['v']
            for y in range(lowerY, height):
                if y > upperY:
                    break
                lowerX = max([0, yLine[1] - minX - base['h']])
                upperX = yLine[2] - minX + base['h']
                for x in range(lowerX, width):
                    if x > upperX:
                        break
                    grid[y * width + x] = UNWALKABLE
        
        for xLine in gGeo['x_lines']:
            lowerX = max([0, xLine[0] - minX - base['h']])
            upperX = xLine[0] - minX + base['h']
            for x in range(lowerX, width):
                if x > upperX:
                    break
                lowerY = max([0, xLine[1] - minY - base['vn']])
                upperY = xLine[2] - minY + base['v']
                for y in range(lowerY, height):
                    if y > upperY:
                        break
                    grid[y * width + x] = UNWALKABLE
        
        for spawn in gMap['spawns']:
            x = math.trunc(spawn[0]) - minX
            y = math.trunc(spawn[1]) - minY
            if grid[y * width + x] == WALKABLE:
                continue
            stack = [[y,x]]
            while len(stack) > 0:
                [y,x] = stack.pop()
                while x >= 0 and grid[y * width + x] == UNKNOWN:
                    x -= 1
                x += 1
                spanAbove = 0
                spanBelow = 0
                while x < width and grid[y * width + x] == UNKNOWN:
                    grid[y * width + x] = WALKABLE
                    if not spanAbove and y > 0 and grid[(y - 1) * width + x] == UNKNOWN:
                        stack.append([y - 1, x])
                        spanAbove = 1
                    elif spanAbove and y > 0 and grid[(y - 1) * width + x] != UNKNOWN:
                        spanAbove = 0
                    
                    if not spanBelow and y < (height - 1) and grid[(y + 1) * width + x] == UNKNOWN:
                        stack.append([y + 1, x])
                        spanBelow = 1
                    elif spanBelow and y < (height - 1) and grid[(y + 1) * width + x] != UNKNOWN:
                        spanBelow = 0
                    x += 1
        Pathfinder.grids[map] = grid

        walkableNodes = []
        points = []

        #beginUpdate?
        
        for y in range(1, height - 1):
            for x in range(1, width):
                mC = grid[y * width + x]
                if mC != WALKABLE:
                    continue

                bL = grid[(y - 1) * width + x - 1]
                bC = grid[(y - 1) * width + x]
                bR = grid[(y - 1) * width + x + 1]
                mL = grid[y * width + x - 1]
                mR = grid[y * width + x + 1]
                uL = grid[(y + 1) * width + x - 1]
                uC = grid[(y + 1) * width + x]
                uR = grid[(y + 1) * width + x + 1]

                mapX = x + minX
                mapY = y + minY

                if (bL == UNWALKABLE) and (bC == UNWALKABLE) and (bR == UNWALKABLE) and (mL == UNWALKABLE) and (uL == UNWALKABLE):
                    walkableNodes.append(Pathfinder.addNodeToGraph(map, mapX, mapY))
                    points.append([mapX, mapY])
                elif (bL == UNWALKABLE) and (bC == UNWALKABLE) and (bR == UNWALKABLE) and (mR == UNWALKABLE) and (uR == UNWALKABLE):
                    walkableNodes.append(Pathfinder.addNodeToGraph(map, mapX, mapY))
                    points.append([mapX, mapY])
                elif (bR == UNWALKABLE) and (mR == UNWALKABLE) and (uL == UNWALKABLE) and (uC == UNWALKABLE) and (uR == UNWALKABLE):
                    walkableNodes.append(Pathfinder.addNodeToGraph(map, mapX, mapY))
                    points.append([mapX, mapY])
                elif (bL == UNWALKABLE) and (mL == UNWALKABLE) and (uL == UNWALKABLE) and (uC == UNWALKABLE) and (uR == UNWALKABLE):
                    walkableNodes.append(Pathfinder.addNodeToGraph(map, mapX, mapY))
                    points.append([mapX, mapY])
                elif (bL == UNWALKABLE) and (bC == WALKABLE) and (mL == WALKABLE):
                    walkableNodes.append(Pathfinder.addNodeToGraph(map, mapX, mapY))
                    points.append([mapX, mapY])
                elif (bC == WALKABLE) and (bR == UNWALKABLE) and (mR == WALKABLE):
                    walkableNodes.append(Pathfinder.addNodeToGraph(map, mapX, mapY))
                    points.append([mapX, mapY])
                elif (mR == WALKABLE) and (uC == WALKABLE) and (uR == UNWALKABLE):
                    walkableNodes.append(Pathfinder.addNodeToGraph(map, mapX, mapY))
                    points.append([mapX, mapY])
                elif (mL == WALKABLE) and (uL == UNWALKABLE) and (uC == WALKABLE):
                    walkableNodes.append(Pathfinder.addNodeToGraph(map, mapX, mapY))
                    points.append([mapX, mapY])
        
        transporters = []
        for npc in gMap['npcs']:
            if npc['id'] != 'transporter':
                continue
            closest = Pathfinder.findClosestSpawn(map, npc['position'][0], npc['position'][1])
            fromNode = Pathfinder.addNodeToGraph(map, closest['x'], closest['y'])
            points.append([closest['x'], closest['y']])
            walkableNodes.append(fromNode)
            transporters.append(npc)

            angle = 0
            while angle < math.pi * 2:
                x = math.trunc(npc['position'][0] + math.cos(angle) * (Constants.TRANSPORTER_REACH_DISTANCE - 10))
                y = math.trunc(npc['position'][1] + math.sin(angle) * (Constants.TRANSPORTER_REACH_DISTANCE - 10))
                if Pathfinder.canStand({'map': map, 'x': x, 'y': y}):
                    fromNode = Pathfinder.addNodeToGraph(map, x, y)
                    points.append([x, y])
                    walkableNodes.append(fromNode)
                angle += math.pi / 32
        
        doors = []
        for door in gMap['doors']:
            if len(door) > 7 and door[7] == 'complicated':
                continue

            spawn = gMap['spawns'][door[6]]
            fromDoor = Pathfinder.addNodeToGraph(map, spawn[0], spawn[1])
            points.append([spawn[0], spawn[1]])
            walkableNodes.append(fromDoor)
            doors.append(door)

            doorX = door[0]
            doorY = door[1]
            doorWidth = door[2]
            doorHeight = door[3]
            doorCorners = [
                { 'x': doorX - (doorWidth / 2), 'y': doorY - (doorHeight / 2) }, # Top left
                { 'x': doorX + (doorWidth / 2), 'y': doorY - (doorHeight / 2) }, # Top right
                { 'x': doorX - (doorWidth / 2), 'y': doorY + (doorHeight / 2) }, # Bottom right
                { 'x': doorX + (doorWidth / 2), 'y': doorY + (doorHeight / 2) }  # Bottom left
            ]
            for point in doorCorners:
                angle = 0
                while angle < math.pi * 2:
                    x = math.trunc(point['x'] + math.cos(angle) * (Constants.DOOR_REACH_DISTANCE - 10))
                    y = math.trunc(point['y'] + math.sin(angle) * (Constants.DOOR_REACH_DISTANCE - 10))
                    if Pathfinder.canStand({ 'map': map, 'x': x, 'y': y }):
                        fromNode = Pathfinder.addNodeToGraph(map, x, y)
                        points.append([x, y])
                        walkableNodes.append(fromNode)
                    angle += math.pi / 32
        
        townNode = Pathfinder.addNodeToGraph(map, gMap['spawns'][0][0], gMap['spawns'][0][1])
        walkableNodes.append(townNode)
        points.append([townNode['x'], townNode['y']])
        townLinkData = { 'map': map, 'type': 'town', 'x': townNode['x'], 'y': townNode['y'] }
        for i in range(1, len(gMap['spawns'])):
            spawn = gMap['spawns'][i]
            node = Pathfinder.addNodeToGraph(map, spawn[0], spawn[1])
            walkableNodes.append(node)
            points.append([node['x'], node['y']])
        wnStart = datetime.now()
        print("num walkableNodes: ", len(walkableNodes))
        for fromNode in walkableNodes:
            for door in doors:
                if Pathfinder.doorDistance(fromNode, door) >= Constants.DOOR_REACH_DISTANCE:
                    continue

                spawn2 = Pathfinder.G['maps'][door[4]]['spawns'][door[5]]
                toDoor = Pathfinder.addNodeToGraph(door[4], spawn2[0], spawn2[1])
                if len(door) > 7 and door[7] == 'key':
                    #TODO: see if nodes need to be referenced by their indices
                    Pathfinder.addLinkToGraph(fromNode, toDoor, { 'key': door[8], 'map': toDoor['map'], 'type': 'enter', 'x': toDoor['x'], 'y': toDoor['y'] })
                else:
                    #TODO: see if nodes need to be referenced by their indices
                    Pathfinder.addLinkToGraph(fromNode, toDoor, { 'map': toDoor['map'], 'spawn': door[5], 'type': 'transport', 'x': toDoor['x'], 'y': toDoor['y'] })
                    
            for npc in transporters:
                if Tools.distance(fromNode, { 'x': npc['position'][0], 'y': npc['position'][1] }) > Constants.TRANSPORTER_REACH_DISTANCE:
                    continue
                for toMap in Pathfinder.G['npcs']['transporter']['places']:
                    if map == toMap:
                        continue

                    spawnID = Pathfinder.G['npcs']['transporter']['places'][toMap]
                    spawn = Pathfinder.G['maps'][toMap]['spawns'][spawnID]
                    toNode = Pathfinder.addNodeToGraph(toMap, spawn[0], spawn[1])

                    Pathfinder.addLinkToGraph(fromNode, toNode, { 'map': toMap, 'spawn': spawnID, 'type': 'transport', 'x': toNode['x'], 'y': toNode['y'] })
        print("walkableNodes processing time: ", (datetime.now() - wnStart).total_seconds())
        
        leaveLink = Pathfinder.addNodeToGraph('main', Pathfinder.G['maps']['main']['spawns'][0][0], Pathfinder.G['maps']['main']['spawns'][0][1])
        leaveLinkData = { 'map': leaveLink['map'], 'type': 'leave', 'x': leaveLink['x'], 'y': leaveLink['y'] }
        for node in walkableNodes:
            if node != townNode:
                Pathfinder.addLinkToGraph(node, townNode, townLinkData)
            
            if map == 'cyberland' or map == 'jail':
                Pathfinder.addLinkToGraph(node, leaveLink, leaveLinkData)

        delaunay = Delaunator(points)
        
        for i in range(0, len(delaunay.halfedges)):
            halfedge = delaunay.halfedges[i]
            if halfedge < i:
                continue
            ti = delaunay.triangles[i]
            tj = delaunay.triangles[halfedge]

            x1 = delaunay.coords[ti * 2]
            y1 = delaunay.coords[ti * 2 + 1]
            x2 = delaunay.coords[tj * 2]
            y2 = delaunay.coords[tj * 2 + 1]

            name1 = f"{map}:{x1},{y1}"
            name2 = f"{map}:{x2},{y2}"
            node1 = Pathfinder.graph.vs.select(name_eq=name1)[0]
            node2 = Pathfinder.graph.vs.select(name_eq=name2)[0]
            if Pathfinder.canWalkPath({ 'map': map, 'x': x1, 'y': y1 }, { 'map': map, 'x': x2, 'y': y2 }):
                Pathfinder.addLinkToGraph(node1, node2)
                Pathfinder.addLinkToGraph(node2, node1)
            
        return grid
    
    @staticmethod
    def findClosestNode(map: str, x: int, y: int):
        closest = { 'distance': sys.maxsize, 'node': None }
        closestWalkable = { 'distance': sys.maxsize, 'node': None }
        _from = { 'map': map, 'x': x, 'y': y}
        for node in Pathfinder.graph.vs:
            if node['map'] == map:
                distance = Tools.distance(_from, node)

                if distance > closest['distance']:
                    continue

                walkable = Pathfinder.canWalkPath(_from, node)

                if distance < closest['distance']:
                    closest['distance'] = distance
                    closest['node'] = node
                if walkable and distance < closestWalkable['distance']:
                    closestWalkable['distance'] = distance
                    closestWalkable['node'] = node
                if distance < 1:
                    break
        
        if closestWalkable['node'] != None:
            return closestWalkable['node']
        else:
            return closest['node']
    
    @staticmethod
    def findClosestSpawn(map: str, x: int, y: int):
        closest = { 'distance': sys.maxsize, 'map': map, 'x': sys.maxsize, 'y': sys.maxsize }
        for spawn in Pathfinder.G['maps'][map]['spawns']:
            distance = Tools.distance({ 'x': x, 'y': y }, { 'x': spawn[0], 'y': spawn[1] })
            if distance < closest['distance']:
                closest['x'] = spawn[0]
                closest['y'] = spawn[1]
                closest['distance'] = distance
        
        return closest

    @staticmethod
    def getPath(fr, to, *, avoidTownWarps: bool = False, getWithin: int = None, useBlink: bool = False, costs = {}):
        if not Pathfinder.G:
            raise Exception("Prepaire pathfinding before querying getPath()!")
        
        if (fr['map'] == to['map']) and (Pathfinder.canWalkPath(fr, to)) and (Tools.distance(fr, to) < Pathfinder.TOWN_COST):
            return [{ 'map': fr['map'], 'type': 'move', 'x': fr['x'], 'y': fr['y'] }, { 'map': to['map'], 'type': 'move', 'x': to['x'], 'y': to['y'] }]
        
        fromNode = Pathfinder.findClosestNode(fr['map'], fr['x'], fr['y'])
        toNode = Pathfinder.findClosestNode(to['map'], to['x'], to['y'])

        path = []

        rawPath = Pathfinder.graph.get_shortest_paths(fromNode, to=toNode, mode='out', output='vpath')[0]

        if len(rawPath) == 0:
            raise Exception("We did not find a path...")

        path.append({ 'map': fromNode['map'], 'type': 'move', 'x': fromNode['x'], 'y': fromNode['y'] })
        for i in range((len(rawPath) - 1), 0, -1):
            currentNode = rawPath[i]
            nextNode = rawPath[i - 1]

            lowestCostLinkData = None
            lowestCost = sys.maxsize
            for link in Pathfinder.graph.es.select(source_eq = currentNode.index):
                if link.target != nextNode.index:
                    continue
                cost = Pathfinder.computeLinkCost(fromNode, toNode, link, avoidTownWarps=avoidTownWarps, costs=costs)
                if (cost < lowestCost) or ((cost == lowestCost) and ((link != None) and (link['data']['type'] == 'move'))):
                    lowestCost = cost
                    lowestCostLinkData = link['data']
            
            if lowestCostLinkData != None:
                path.append(lowestCostLinkData)
                if lowestCostLinkData['type'] == 'town':
                    path.append({ 'map': lowestCostLinkData['map'], 'type': 'move', 'x': nextNode['x'], 'y': nextNode['y'] })
            else:
                path.append({ 'map': nextNode['map'], 'type': 'move', 'x': nextNode['x'], 'y': nextNode['y'] })
        path.append({ 'map': toNode['map'], 'type': 'move', 'x': toNode['x'], 'y': toNode['y'] })

        for i in range(0, len(path) - 1):
            current = path[i]
            next = path[i + 1]

            if current['type'] != next['type']:
                continue
            if current['map'] != next['map']:
                continue
            if current['x'] != next['x']:
                continue
            if current['y'] != next['y']:
                continue

            path.pop(i)

        return path
    
    @staticmethod
    def getSafeWalkTo(fr, to):
        if fr['map'] != to['map']:
            raise Exception("We can't walk across maps.")
        if not Pathfinder.G:
            raise Exception("Prepare pathfinding beofre querying getSafeWalkTo()!")

        grid = Pathfinder.getGrid(fr['map'])
        gGeo = Pathfinder.G['geometry'][fr['map']]
        width = gGeo['max_x'] - gGeo['min_x']

        xStep = None
        yStep = None
        error = None
        errorPrev = None

        x = math.trunc(fr['x']) - gGeo['min_x']
        y = math.trunc(fr['y']) - gGeo['min_y']
        dx = math.trunc(to['x']) - math.trunc(fr['x'])
        dy = math.trunc(to['y']) - math.trunc(fr['y'])

        if grid[y * width + x] != WALKABLE:
            print(f"We shouldn't be able to be where we are in from ({fr['map']}:{fr['x']},{fr['y']}).")
            return Pathfinder.findClosestNode(fr['map'], fr['x'], fr['y'])
        
        if dy < 0:
            yStep = -1
            dy = -dy
        else:
            yStep = 1
        if dx < 0:
            xStep = -1
            dx = -dx
        else:
            xStep = 1
        ddy = 2 * dy
        ddx = 2 * dx

        if ddx >= ddy:
            errorPrev = error = dx
            for i in range(0, dx):
                x += xStep
                error += ddy
                if error > ddx:
                    y += yStep
                    error -= ddx
                    if error + errorPrev < ddx:
                        if grid[(y - yStep) * width + x] != WALKABLE:
                            return { 'map': fr['map'], 'x': x - xStep + gGeo['min_x'], 'y': y - yStep + gGeo['min_y'] }
                    elif error + errorPrev > ddx:
                        if grid[y * width + x - xStep] != WALKABLE:
                            return { 'map': fr['map'], 'x': x - xStep + gGeo['min_x'], 'y': y - yStep + gGeo['min_y'] }
                    else:
                        if grid[(y - yStep) * width + x] != WALKABLE:
                            return { 'map': fr['map'], 'x': x - xStep + gGeo['min_x'], 'y': y - yStep + gGeo['min_y'] }
                        if grid[y * width + x - xStep] != WALKABLE:
                            return { 'map': fr['map'], 'x': x - xStep + gGeo['min_x'], 'y': y - yStep + gGeo['min_y'] }
                if grid[y * width + x] != WALKABLE:
                    return { 'map': fr['map'], 'x': x - xStep + gGeo['min_x'], 'y': y + gGeo['min_y'] }
                errorPrev = error
        else:
            errorPrev = error = dy
            for i in range(0, dy):
                y += yStep
                error += ddx
                if error > ddy:
                    x += xStep
                    error -= ddy
                    if error + errorPrev < ddy:
                        if grid[y * width + x - xStep] != WALKABLE:
                            return { 'map': fr['map'], 'x': x - xStep + gGeo['min_x'], 'y': y - yStep + gGeo['min_y'] }
                    elif error + errorPrev > ddy:
                        if grid[(y - yStep) * width + x] != WALKABLE:
                            return { 'map': fr['map'], 'x': x - xStep + gGeo['min_x'], 'y': y - yStep + gGeo['min_y'] }
                    else:
                        if grid[y * width + x - xStep] != WALKABLE:
                            return { 'map': fr['map'], 'x': x - xStep + gGeo['min_x'], 'y': y - yStep + gGeo['min_y'] }
                        if grid[(y - yStep) * width + x] != WALKABLE:
                            return { 'map': fr['map'], 'x': x - xStep + gGeo['min_x'], 'y': y - yStep + gGeo['min_y'] }
                if grid[y * width + x] != WALKABLE:
                    return { 'map': fr['map'], 'x': x + gGeo['min_x'], 'y': y - yStep + gGeo['min_y'] }
                errorPrev = error
        
        return to

    @staticmethod
    async def prepare(g, *, base = {}, cheat = False, include_bank_b = False, include_bank_u = False, include_test = False):
        Pathfinder.G = g

        maps = [Constants.PATHFINDER_FIRST_MAP]

        start = datetime.now()

        i = 0
        while i < len(maps):
            map = maps[i]

            for door in Pathfinder.G['maps'][map]['doors']:
                if door[4] == 'bank_b' and not include_bank_b:
                    continue
                if door[4] == 'bank_u' and not include_bank_u:
                    continue
                if door[4] == 'test' and not include_test:
                    continue
                if door[4] not in maps:
                    maps.append(door[4])
            
            i += 1
        
        for map in Pathfinder.G['npcs']['transporter']['places'].keys():
            if map == 'test' and not include_test:
                continue
            if map not in maps:
                maps.append(map)

        for map in maps:
            if map == 'test' and not include_test:
                continue
            if base:
                Pathfinder.getGrid(map, base = base)
            else:
                Pathfinder.getGrid(map)
        if base:
            Pathfinder.getGrid('jail', base = base)
        else:
            Pathfinder.getGrid('jail')
        
        if cheat:
            if 'winterland' in maps:
                fr = Pathfinder.findClosestNode('winterland', 721, 277)
                to = Pathfinder.findClosestNode('winterland', 737, 352)
                if fr != None and to != None and fr != to:
                    Pathfinder.addLinkToGraph(fr, to)
                else:
                    print('The winterland map has changed, cheat to walk to icegolem is not enabled.')

        print(f"Pathfinding prepared! ({(datetime.now() - start).total_seconds()}s)")
        print(f"  # Nodes: {len(Pathfinder.graph.vs)}")
        print(f"  # Links: {len(Pathfinder.graph.es)}")